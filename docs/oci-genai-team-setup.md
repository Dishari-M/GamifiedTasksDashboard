# Temporary OCI GenAI Test Setup

This guide documents the temporary local setup pattern used to verify access to OCI Generative AI for DevQuest Phase 8 testing.

This is not the final DevQuest OCI GenAI compartment or production setup. The final compartment, model, and auth details are expected to be shared by the team later.

Do not commit private keys, passphrases, or personal OCI config files to this repository.

## Verified Access

The temporary test compartment was verified as accessible with a teammate-provided OCI API key setup.

```text
config_valid=YES
compartment_visible=YES
compartment_name=FBGBU-SIMPHONY-DEV
compartment_state=ACTIVE
genai_models_accessible=YES
genai_status=200
model_sample_count=106
```

Summary:

```text
Region: us-ashburn-1
Compartment name: FBGBU-SIMPHONY-DEV
Compartment state: ACTIVE
GenAI model listing: accessible
Model sample count: 106
```

Compartment OCID:

```text
ocid1.compartment.oc1..aaaaaaaawbtthodv5qt2lvexm7vv7eu3bxwwmvxyut3yxoj24mznw2xb2noa
```

Service endpoint:

```text
https://inference.generativeai.us-ashburn-1.oci.oraclecloud.com
```

## Local Key Folder

For temporary local testing, place the teammate-provided OCI key files outside the repo, for example:

```text
%USERPROFILE%\.oci_mohit\oci_api_key.pem
%USERPROFILE%\.oci_mohit\oci_api_key_public.pem
```

The private key file must remain local and must not be committed.

## Required Local Values

Before a teammate can use this setup locally, they need the following values from the person/team managing the temporary OCI access:

```text
user OCID
tenancy OCID
compartment OCID
region
private key file
public key file, optional but useful for fingerprint checks
key fingerprint
private key passphrase, if the key is encrypted
GenAI inference endpoint
GenAI model ID
```

Each teammate must update these locally:

```text
key_file path
fingerprint
pass_phrase
OCI_REGION
OCI_COMPARTMENT_ID
OCI_GENAI_ENDPOINT
OCI_GENAI_MODEL_ID
```

If using an OCI config profile instead of an inline Python dict, the local config file also needs:

```ini
[DEFAULT]
user=<USER_OCID>
fingerprint=<KEY_FINGERPRINT>
key_file=<ABSOLUTE_PATH_TO_PRIVATE_KEY>
tenancy=<TENANCY_OCID>
region=us-ashburn-1
pass_phrase=<PRIVATE_KEY_PASSPHRASE>
```

Recommended local config path:

```text
%USERPROFILE%\.oci\config
```

If teammates do not want to overwrite their normal OCI profile, create a separate profile name such as:

```ini
[DEVQUEST_TEMP_GENAI]
user=<USER_OCID>
fingerprint=<KEY_FINGERPRINT>
key_file=<ABSOLUTE_PATH_TO_PRIVATE_KEY>
tenancy=<TENANCY_OCID>
region=us-ashburn-1
pass_phrase=<PRIVATE_KEY_PASSPHRASE>
```

Then set:

```powershell
$env:OCI_CONFIG_PROFILE="DEVQUEST_TEMP_GENAI"
```

## Config Values

Use this Python SDK config shape for temporary testing, replacing placeholders with the current test values:

```python
import os

config = {
    "user": "<USER_OCID>",
    "key_file": os.path.expanduser(r"~\.oci_mohit\oci_api_key.pem"),
    "fingerprint": "<KEY_FINGERPRINT>",
    "tenancy": "<TENANCY_OCID>",
    "region": "us-ashburn-1",
    "pass_phrase": "<PRIVATE_KEY_PASSPHRASE>",
}

compartment_id = "ocid1.compartment.oc1..aaaaaaaawbtthodv5qt2lvexm7vv7eu3bxwwmvxyut3yxoj24mznw2xb2noa"
endpoint = "https://inference.generativeai.us-ashburn-1.oci.oraclecloud.com"
```

The verified key fingerprint for the local public key was:

```text
27:28:50:ab:25:4d:7c:0f:da:1a:92:e5:59:b0:d8:44
```

If a pasted fingerprint differs, derive it from the public key rather than guessing.

## Verification Script

Run this from the repo root after installing backend dependencies:

```powershell
@'
import os
import oci
from oci.identity import IdentityClient
from oci.generative_ai import GenerativeAiClient

compartment_id = "ocid1.compartment.oc1..aaaaaaaawbtthodv5qt2lvexm7vv7eu3bxwwmvxyut3yxoj24mznw2xb2noa"

config = {
    "user": "<USER_OCID>",
    "key_file": os.path.expanduser(r"~\.oci_mohit\oci_api_key.pem"),
    "fingerprint": "<KEY_FINGERPRINT>",
    "tenancy": "<TENANCY_OCID>",
    "region": "us-ashburn-1",
    "pass_phrase": "<PRIVATE_KEY_PASSPHRASE>",
}

oci.config.validate_config(config)

identity = IdentityClient(config)
compartment = identity.get_compartment(compartment_id).data
print("compartment_name=" + compartment.name)
print("compartment_state=" + compartment.lifecycle_state)

genai = GenerativeAiClient(config)
models = genai.list_models(compartment_id=compartment_id, limit=5).data.items
print("model_sample_count=" + str(len(models)))
for model in models:
    print("model=" + str(model.display_name or model.id))
'@ | backend\.venv\Scripts\python.exe -
```

Expected result:

```text
compartment_name=FBGBU-SIMPHONY-DEV
compartment_state=ACTIVE
model_sample_count=<non-zero>
```

## App Environment Variables

Set these in PowerShell before starting the backend process. They are not code config values and should not be committed to the repository.

For DevQuest real AI mode against the temporary test compartment, use:

```powershell
$env:DEVQUEST_AI_MODE="real"
$env:DEVQUEST_AI_PROVIDER="oci_genai"
$env:OCI_AUTH_TYPE="config_file"
$env:OCI_REGION="us-ashburn-1"
$env:OCI_COMPARTMENT_ID="ocid1.compartment.oc1..aaaaaaaawbtthodv5qt2lvexm7vv7eu3bxwwmvxyut3yxoj24mznw2xb2noa"
$env:OCI_GENAI_ENDPOINT="https://inference.generativeai.us-ashburn-1.oci.oraclecloud.com"
$env:OCI_GENAI_SERVING_MODE="on_demand"
$env:OCI_GENAI_REQUEST_FORMAT="generic"
$env:OCI_GENAI_MODEL_ID="<MODEL_ID>"
```

Current Phase 8 code supports `config_file`, `api_key`, `instance_principal`, and `resource_principal` auth modes. Prefer `config_file` for normal team use. If using this local key folder directly for temporary testing, use `api_key` only through local environment variables and do not commit secrets.

Temporary direct API-key env example:

```powershell
$env:DEVQUEST_AI_MODE="real"
$env:DEVQUEST_AI_PROVIDER="oci_genai"
$env:OCI_AUTH_TYPE="api_key"
$env:OCI_REGION="us-ashburn-1"
$env:OCI_USER_OCID="<USER_OCID>"
$env:OCI_TENANCY_OCID="<TENANCY_OCID>"
$env:OCI_KEY_FILE="$env:USERPROFILE\.oci_mohit\oci_api_key.pem"
$env:OCI_KEY_FINGERPRINT="<KEY_FINGERPRINT>"
$env:OCI_KEY_PASSPHRASE="<PRIVATE_KEY_PASSPHRASE>"
$env:OCI_COMPARTMENT_ID="ocid1.compartment.oc1..aaaaaaaawbtthodv5qt2lvexm7vv7eu3bxwwmvxyut3yxoj24mznw2xb2noa"
$env:OCI_GENAI_ENDPOINT="https://inference.generativeai.us-ashburn-1.oci.oraclecloud.com"
$env:OCI_GENAI_SERVING_MODE="on_demand"
$env:OCI_GENAI_REQUEST_FORMAT="generic"
$env:OCI_GENAI_MODEL_ID="openai.gpt-5.4-mini"
```

When the final team compartment is shared, replace the temporary values in this document with the final approved compartment ID, endpoint, model ID, and auth instructions.

## Switch And Fallback Reference

These flags decide whether the app uses mock data, real Oracle-backed data, mock AI, or real OCI GenAI. Keep these defaults safe so teammates without OCI access can still run the app.

| Setting | Safe default | Temporary test value | Meaning |
| --- | --- | --- | --- |
| `DEVQUEST_DATA_MODE` | `mock` | `mock` | Uses local Phase 8 Python mock data. `oracle` is reserved for later repository implementation. |
| `DEVQUEST_AI_MODE` | `mock` | `real` only when testing OCI | `mock` returns deterministic local insight. `real` calls OCI GenAI. |
| `DEVQUEST_AI_PROVIDER` | `oci_genai` | `oci_genai` | Approved provider name. Other values are unsupported. |
| `OCI_AUTH_TYPE` | `config_file` | `api_key` for this temporary folder setup | Auth method for real AI. Use `config_file` for normal OCI profile setup. |
| `OCI_REGION` | empty | `us-ashburn-1` | Required for direct `api_key` auth. |
| `OCI_CONFIG_PROFILE` | `DEFAULT` | optional profile name | Used only with `OCI_AUTH_TYPE=config_file`. |
| `OCI_USER_OCID` | empty | teammate-provided user OCID | Required only with temporary `api_key` auth. |
| `OCI_TENANCY_OCID` | empty | teammate-provided tenancy OCID | Required only with temporary `api_key` auth. |
| `OCI_KEY_FILE` | empty | `%USERPROFILE%\.oci_mohit\oci_api_key.pem` | Required only with temporary `api_key` auth. |
| `OCI_KEY_FINGERPRINT` | empty | verified key fingerprint | Required only with temporary `api_key` auth. |
| `OCI_KEY_PASSPHRASE` | empty | teammate-provided passphrase | Needed only when the private key is encrypted. |
| `OCI_COMPARTMENT_ID` | empty | temporary compartment OCID | Required for `DEVQUEST_AI_MODE=real`. |
| `OCI_GENAI_ENDPOINT` | empty | `https://inference.generativeai.us-ashburn-1.oci.oraclecloud.com` | Endpoint override for temporary testing. |
| `OCI_GENAI_SERVING_MODE` | `on_demand` | `on_demand` | Use hosted model IDs. `dedicated` expects a dedicated endpoint ID. |
| `OCI_GENAI_MODEL_ID` | empty | `openai.gpt-5.4-mini` | Model used by real dashboard AI insight. |
| `OCI_GENAI_REQUEST_FORMAT` | `generic` | `generic` | Use `generic` for OpenAI/Gemini/xAI models, `cohere` for Cohere, or `auto`. |
| `REACT_APP_API_BASE_URL` | empty | optional | Frontend override. If empty, Phase 8 frontend helpers call `http://127.0.0.1:8000/api/v1`. |

Fallback behavior:

| Scenario | Result |
| --- | --- |
| No OCI setup | Keep `DEVQUEST_AI_MODE=mock`; dashboard still works with deterministic insight. |
| Backend down from frontend | Dashboard keeps local React demo data as fallback. |
| `DEVQUEST_DATA_MODE=oracle` before repositories exist | Phase 8 returns `501 Not Implemented`. Use `mock` for now. |
| `DEVQUEST_AI_MODE=real` without model/compartment/auth | Phase 8 returns an HTTP error instead of hiding the config problem. |
| Wrong request format for model | OCI may return provider `400`; use `generic` for OpenAI-style models. |

AI assistant guardrails:

- Never change defaults so real OCI is required for normal local development.
- Never commit key files, passphrases, or personal OCI config values.
- Use this temporary compartment only for smoke tests until the final team compartment is shared.
- Preserve the `/api/v1/dashboard/today` response shape in both mock and real AI modes.
- Prefer `openai.gpt-5.4-mini` for temporary Phase 8 testing because it has already returned a successful inference response.

## Temporary Model Notes

The temporary compartment returned 106 available models. For Phase 8 dashboard insight testing, start with:

```text
openai.gpt-5.4-mini
```

This model was verified with a real inference call and returned:

```text
status=200
model=openai.gpt-5.4-mini
message_role=ASSISTANT
content={"ok": true, "message": "oci genai reachable"}
```

Important SDK note:

```text
OpenAI models on this OCI endpoint require max_completion_tokens instead of max_tokens.
```

The current `backend/integrations/oci_genai_client.py` uses a Cohere-style request. To use `openai.gpt-5.4-mini`, update the real-mode client to use `GenericChatRequest` with `max_completion_tokens`.

Recommended temporary model choices:

| Use case | Suggested model IDs |
| --- | --- |
| Phase 8 dashboard AI insight | `openai.gpt-5.4-mini`, `openai.gpt-5.4-nano`, `google.gemini-2.5-flash-lite` |
| Higher quality summaries | `openai.gpt-5.4`, `openai.gpt-5.5`, `google.gemini-2.5-pro` |
| Reasoning-heavy planning | `openai.o3`, `openai.o4-mini`, `cohere.command-a-reasoning`, `xai.grok-4.20-reasoning` |
| Fast task enrichment | `openai.gpt-4.1-nano`, `openai.gpt-5-nano`, `openai.gpt-5.4-nano` |
| Embeddings/search | `openai.text-embedding-3-small`, `openai.text-embedding-3-large`, `cohere.embed-v4.0` |
| Reranking | `cohere.rerank-v3.5` |
| Image generation | `openai.gpt-image-1`, `openai.gpt-image-1.5` |
| Audio/transcription/TTS | `openai.gpt-4o-transcribe`, `openai.gpt-4o-mini-transcribe`, `openai.gpt-4o-mini-tts`, `openai.gpt-audio` |
| Safety checks | `meta.llama-guard-4-12b`, `protectai.deberta-v3-base-prompt-injection-v2` |

Model aliases observed in the temporary compartment:

```text
cohere.command-a-03-2025
cohere.command-a-reasoning
cohere.command-a-vision
cohere.command-r-08-2024
cohere.command-r-plus-08-2024
cohere.embed-english-image-v3.0
cohere.embed-english-light-image-v3.0
cohere.embed-multilingual-image-v3.0
cohere.embed-multilingual-light-image-v3.0
cohere.embed-multilingual-v3.0
cohere.embed-v4.0
cohere.rerank-v3.5
google.gemini-2.5-flash
google.gemini-2.5-flash-lite
google.gemini-2.5-pro
meta.llama-4-maverick-17b-128e-instruct-fp8
meta.llama-4-scout-17b-16e-instruct
meta.llama-guard-4-12b
openai.gpt-4.1
openai.gpt-4.1-mini
openai.gpt-4.1-nano
openai.gpt-4o
openai.gpt-4o-mini
openai.gpt-4o-mini-search-preview
openai.gpt-4o-mini-transcribe
openai.gpt-4o-mini-tts
openai.gpt-4o-search-preview
openai.gpt-4o-transcribe
openai.gpt-4o-transcribe-diarize
openai.gpt-5
openai.gpt-5-codex
openai.gpt-5-mini
openai.gpt-5-nano
openai.gpt-5.1
openai.gpt-5.1-chat-latest
openai.gpt-5.1-codex
openai.gpt-5.1-codex-max
openai.gpt-5.1-codex-mini
openai.gpt-5.2
openai.gpt-5.2-chat-latest
openai.gpt-5.2-codex
openai.gpt-5.2-pro
openai.gpt-5.3-codex
openai.gpt-5.4
openai.gpt-5.4-mini
openai.gpt-5.4-nano
openai.gpt-5.4-pro
openai.gpt-5.5
openai.gpt-5.5-pro
openai.gpt-audio
openai.gpt-audio-mini
openai.gpt-image-1
openai.gpt-image-1.5
openai.gpt-oss-120b
openai.gpt-oss-20b
openai.gpt-realtime
openai.o1
openai.o3
openai.o3-mini
openai.o4-mini
openai.text-embedding-3-large
openai.text-embedding-3-small
protectai.deberta-v3-base-prompt-injection-v2
xai.grok-3
xai.grok-3-fast
xai.grok-3-mini
xai.grok-3-mini-fast
xai.grok-4
xai.grok-4-1-fast-non-reasoning
xai.grok-4-1-fast-reasoning
xai.grok-4-fast-non-reasoning
xai.grok-4-fast-reasoning
xai.grok-4.20-non-reasoning
xai.grok-4.20-reasoning
xai.grok-4.20-multi-agent
xai.grok-4.3
xai.grok-code-fast-1
xai.grok-voice-agent
```

Some providers also expose date-pinned model IDs. Prefer stable aliases for temporary development unless the team needs reproducibility for a specific test.
