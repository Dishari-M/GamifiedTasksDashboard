import os


def get_data_mode():
    """Return the shared data-source mode for backend services.

    DEVQUEST_DATA_MODE controls where API services read data from:
    - oracle: Oracle ADB repositories, used by default for the integrated app.
    - mock: local deterministic Python data, available only when explicitly selected.
    """
    return os.getenv("DEVQUEST_DATA_MODE", "oracle").strip().lower()


def get_ai_mode():
    """Return whether AI calls should be mocked or sent to a real provider.

    DEVQUEST_AI_MODE controls AI execution:
    - real: call the configured approved AI provider, used by default.
    - mock: return deterministic fallback insights without calling external AI.
    """
    return os.getenv("DEVQUEST_AI_MODE", "real").strip().lower()


def get_ai_provider():
    """Return the approved AI provider name to use when DEVQUEST_AI_MODE=real.

    The current production target is OCI Generative AI via the Inference API,
    represented as oci_genai.
    """
    return os.getenv("DEVQUEST_AI_PROVIDER", "oci_genai").strip().lower()


def get_oci_genai_model_id():
    """Return the OCI Generative AI model identifier for real AI calls."""
    return os.getenv("OCI_GENAI_MODEL_ID", "").strip()


def get_oci_compartment_id():
    """Return the OCI compartment OCID used for Generative AI inference calls."""
    return os.getenv("OCI_COMPARTMENT_ID", "").strip()


def get_oci_config_file():
    """Return the OCI SDK config file path.

    OCI_CONFIG_FILE is optional. When it is not set, the OCI SDK default
    location is used, usually ~/.oci/config.
    """
    return os.getenv("OCI_CONFIG_FILE", "").strip()


def get_oci_config_profile():
    """Return the OCI SDK profile name for local config-file authentication."""
    return os.getenv("OCI_CONFIG_PROFILE", "DEFAULT").strip()


def get_oci_auth_type():
    """Return how the OCI SDK should authenticate real AI calls.

    Supported values:
    - config_file: local developer auth through ~/.oci/config. This is default.
    - security_token: local OCI CLI session auth through a profile that has security_token_file.
    - instance_principal: OCI compute/resource runtime auth.
    - resource_principal: OCI Functions or similar resource principal auth.
    """
    return os.getenv("OCI_AUTH_TYPE", "config_file").strip().lower()


def get_oci_genai_endpoint():
    """Return an optional OCI GenAI Inference service endpoint override.

    Most local runs can leave this empty and let the OCI SDK choose from the
    configured region. Set OCI_GENAI_ENDPOINT only if Oracle provides a
    specific endpoint URL for the hackathon tenancy/region.
    """
    return os.getenv("OCI_GENAI_ENDPOINT", "").strip()


def get_oci_region():
    """Return an optional OCI region for direct API-key auth."""
    return os.getenv("OCI_REGION", "").strip()


def get_oci_genai_serving_mode():
    """Return whether OCI GenAI should use on-demand model or dedicated endpoint.

    Supported values:
    - on_demand: OCI hosted model selected by OCI_GENAI_MODEL_ID. This is default.
    - dedicated: dedicated endpoint selected by OCI_GENAI_MODEL_ID.
    """
    return os.getenv("OCI_GENAI_SERVING_MODE", "on_demand").strip().lower()


def get_oci_genai_request_format():
    """Return the OCI GenAI chat request format.

    Supported values:
    - generic: OpenAI/Gemini/xAI style OCI chat request. This is default.
    - cohere: Cohere-specific OCI chat request.
    - auto: choose cohere only when the model ID starts with cohere.
    """
    return os.getenv("OCI_GENAI_REQUEST_FORMAT", "generic").strip().lower()


def get_oci_user_ocid():
    """Return optional API-key auth user OCID for local temporary testing."""
    return os.getenv("OCI_USER_OCID", "").strip()


def get_oci_tenancy_ocid():
    """Return optional API-key auth tenancy OCID for local temporary testing."""
    return os.getenv("OCI_TENANCY_OCID", "").strip()


def get_oci_key_file():
    """Return optional API-key auth private key file path for local testing."""
    return os.getenv("OCI_KEY_FILE", "").strip()


def get_oci_key_fingerprint():
    """Return optional API-key auth public key fingerprint for local testing."""
    return os.getenv("OCI_KEY_FINGERPRINT", "").strip()


def get_oci_key_passphrase():
    """Return optional API-key auth private key passphrase for local testing."""
    return os.getenv("OCI_KEY_PASSPHRASE", "").strip()
