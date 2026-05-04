import json

from config import (
    get_oci_auth_type,
    get_oci_compartment_id,
    get_oci_config_file,
    get_oci_config_profile,
    get_oci_genai_endpoint,
    get_oci_genai_model_id,
    get_oci_genai_serving_mode,
)


def _load_oci_sdk():
    """Import OCI SDK pieces lazily so mock mode works without OCI installed."""
    try:
        import oci
        from oci.generative_ai_inference import GenerativeAiInferenceClient
        from oci.generative_ai_inference.models import (
            ChatDetails,
            CohereChatRequest,
            DedicatedServingMode,
            OnDemandServingMode,
        )
    except ImportError as exc:
        raise NotImplementedError(
            "OCI SDK is not installed. Run `pip install -r requirements.txt` after adding the `oci` package."
        ) from exc

    return {
        "oci": oci,
        "client": GenerativeAiInferenceClient,
        "chat_details": ChatDetails,
        "chat_request": CohereChatRequest,
        "dedicated_mode": DedicatedServingMode,
        "on_demand_mode": OnDemandServingMode,
    }


def _build_client(sdk):
    """Create an OCI GenAI Inference client from the configured auth mode."""
    auth_type = get_oci_auth_type()
    endpoint = get_oci_genai_endpoint()
    oci = sdk["oci"]

    if auth_type == "config_file":
        config_file = get_oci_config_file()
        profile = get_oci_config_profile()
        try:
            config = oci.config.from_file(file_location=config_file or None, profile_name=profile)
        except Exception as exc:
            raise NotImplementedError(
                "OCI config-file authentication failed. Set OCI_CONFIG_FILE/OCI_CONFIG_PROFILE or use another OCI_AUTH_TYPE."
            ) from exc
        kwargs = {"service_endpoint": endpoint} if endpoint else {}
        return sdk["client"](config, **kwargs)

    if auth_type == "instance_principal":
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        kwargs = {"service_endpoint": endpoint} if endpoint else {}
        return sdk["client"]({}, signer=signer, **kwargs)

    if auth_type == "resource_principal":
        signer = oci.auth.signers.get_resource_principals_signer()
        kwargs = {"service_endpoint": endpoint} if endpoint else {}
        return sdk["client"]({}, signer=signer, **kwargs)

    raise NotImplementedError(
        f"Unsupported OCI_AUTH_TYPE '{auth_type}'. Use 'config_file', 'instance_principal', or 'resource_principal'."
    )


def _build_prompt(prompt_payload):
    """Convert dashboard context into a compact prompt for the GenAI model."""
    return (
        "You are DevQuest, an assistant for a gamified developer task dashboard.\n"
        "Return only valid JSON with these keys: text, capacity_minutes, impact_score.\n"
        "Keep text to one concise sentence and do not invent task names.\n\n"
        f"Dashboard context:\n{json.dumps(prompt_payload, indent=2)}"
    )


def _build_chat_details(sdk, prompt_payload):
    """Build OCI chat request details for the configured model/endpoint."""
    model_id = get_oci_genai_model_id()
    compartment_id = get_oci_compartment_id()
    if not model_id:
        raise NotImplementedError("OCI_GENAI_MODEL_ID is required for OCI Generative AI calls.")
    if not compartment_id:
        raise NotImplementedError("OCI_COMPARTMENT_ID is required for OCI Generative AI calls.")

    chat_request = sdk["chat_request"]()
    chat_request.message = _build_prompt(prompt_payload)
    chat_request.max_tokens = 300
    chat_request.temperature = 0.2
    chat_request.is_stream = False

    serving_mode = get_oci_genai_serving_mode()
    if serving_mode == "on_demand":
        mode = sdk["on_demand_mode"](model_id=model_id)
    elif serving_mode == "dedicated":
        mode = sdk["dedicated_mode"](endpoint_id=model_id)
    else:
        raise NotImplementedError(
            f"Unsupported OCI_GENAI_SERVING_MODE '{serving_mode}'. Use 'on_demand' or 'dedicated'."
        )

    chat_details = sdk["chat_details"]()
    chat_details.compartment_id = compartment_id
    chat_details.serving_mode = mode
    chat_details.chat_request = chat_request
    return chat_details


def _read_attr(value, name):
    """Read an attribute from OCI model objects or dict responses."""
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _extract_text_from_response(response_data):
    """Extract generated text from the common OCI GenAI chat response shapes."""
    chat_response = _read_attr(response_data, "chat_response")
    if chat_response:
        text = _read_attr(chat_response, "text") or _read_attr(chat_response, "message")
        if text:
            return text

        choices = _read_attr(chat_response, "choices") or []
        if choices:
            message = _read_attr(choices[0], "message")
            content = _read_attr(message, "content") if message else None
            if isinstance(content, list) and content:
                return _read_attr(content[0], "text") or str(content[0])
            if content:
                return str(content)

    text = _read_attr(response_data, "text")
    if text:
        return text

    if hasattr(response_data, "to_dict"):
        return json.dumps(response_data.to_dict())
    return str(response_data)


def _parse_json_text(text):
    """Parse JSON from model output, accepting simple fenced-code wrappers."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def _normalize_insight(text, prompt_payload):
    """Normalize AI output to the dashboard API contract."""
    try:
        parsed = _parse_json_text(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        parsed = {"text": text}

    capacity = prompt_payload.get("capacity", {})
    top_missions = prompt_payload.get("top_missions", [])
    tasks = prompt_payload.get("tasks", [])

    fallback_text = "Review today's highest impact work and protect the next available focus window."
    if top_missions:
        fallback_text = f"Start with {top_missions[0].get('title', 'the top mission')} during your next focus window."

    return {
        "text": str(parsed.get("text") or fallback_text),
        "capacity_minutes": int(parsed.get("capacity_minutes") or capacity.get("available_focus_minutes") or 0),
        "impact_score": float(
            parsed.get("impact_score")
            or max((task.get("ai_impact_score", 0) for task in tasks), default=0)
            or 0
        ),
    }


def generate_dashboard_insight(prompt_payload):
    """Generate dashboard insight through OCI Generative AI Inference.

    This function is used only when DEVQUEST_AI_MODE=real. It keeps the
    external OCI response behind a stable internal contract so the frontend API
    shape does not change when mock AI is replaced with real AI.
    """
    sdk = _load_oci_sdk()
    chat_details = _build_chat_details(sdk, prompt_payload)
    client = _build_client(sdk)
    response = client.chat(chat_details)
    text = _extract_text_from_response(response.data)
    return _normalize_insight(text, prompt_payload)
