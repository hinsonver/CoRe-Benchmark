"""Credential-safe configuration and optional model-catalogue checks.

Only lookup_model can contact a service, after explicit network consent. Nothing
here loads .env, imports a model SDK, reads replies or sends a generation prompt.
"""
from datetime import datetime, timezone
import json
import os
import urllib.error
import urllib.parse
import urllib.request


def _connection(model, environ):
    provider = model.split(":", 1)[0] if model else None
    if provider == "openai":
        key_name = "GPT_API_KEY" if not environ.get("OPENAI_API_KEY") and environ.get("GPT_API_KEY") else "OPENAI_API_KEY"
        return environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1", environ.get(key_name), key_name
    if provider == "custom":
        return environ.get("CUSTOM_BASE_URL"), environ.get("CUSTOM_API_KEY"), "CUSTOM_API_KEY"
    if provider in ("local", "localbase"):
        return environ.get("LOCAL_BASE_URL"), environ.get("LOCAL_API_KEY"), "LOCAL_API_KEY"
    return None, None, None


def configuration(model, environ=None):
    """Return names/status only; never return a credential or endpoint value."""
    env = os.environ if environ is None else environ
    provider = model.split(":", 1)[0] if model else None
    if not model:
        return {"status": "not_applicable", "required_environment": [], "environment_present": {}, "issues": []}
    endpoint, key, key_name = _connection(model, env)
    required = (["LOCAL_BASE_URL"] if provider in ("local", "localbase") else
                ["CUSTOM_BASE_URL", "CUSTOM_API_KEY"] if provider == "custom" else
                [key_name] if provider == "openai" else [])
    issues = ["missing environment variable: " + name for name in required if not env.get(name, "").strip()]
    invalid = []
    if provider not in ("custom", "openai", "local", "localbase"):
        invalid.append("unsupported execution provider")
    if endpoint:
        try:
            url = urllib.parse.urlsplit(endpoint)
            valid = (bool(url.hostname) and url.port != 0 and url.scheme in ("https", "http")
                     and not url.username and not url.password and not url.query and not url.fragment
                     and not any(c.isspace() or ord(c) < 32 for c in endpoint))
            if provider in ("custom", "openai") and url.scheme != "https":
                valid = valid and url.hostname in ("127.0.0.1", "localhost", "::1")
        except ValueError:
            valid = False
        if not valid:
            invalid.append("invalid endpoint configuration: require HTTPS (or loopback HTTP), without embedded credentials, query or fragment")
    if key and (any(c.isspace() for c in key) or key.lower() in ("empty", "your_api_key", "changeme")):
        invalid.append("invalid credential configuration: " + key_name)
    extra_name = "CUSTOM_EXTRA_BODY" if provider == "custom" else "LOCAL_EXTRA_BODY" if provider == "local" else None
    if extra_name and env.get(extra_name):
        try:
            extra = json.loads(env[extra_name])
            if not isinstance(extra, dict):
                raise ValueError("object required")
            if set(extra) & {"model", "messages", "prompt", "headers", "extra_headers", "api_key", "base_url",
                             "temperature", "max_tokens", "max_completion_tokens", "stop"}:
                raise ValueError("cannot override model, credentials or frozen request arguments")
            archived_extras = {"custom:deepseek/deepseek-v4-pro": {"thinking": {"type": "disabled"}},
                               "custom:qwen/qwen3.8-max": {"enable_thinking": False},
                               "custom:z-ai/glm-5.3": {"reasoning_effort": "low"}}
            if provider == "custom" and extra != archived_extras.get(model):
                raise ValueError("custom body differs from frozen inference settings")
        except (ValueError, TypeError):
            invalid.append("invalid JSON object configuration: " + extra_name)
    return {"status": "invalid" if invalid else "incomplete" if issues else "configured",
            "provider": provider, "required_environment": required,
            "environment_present": {name: bool(env.get(name, "").strip()) for name in required},
            "credential_source": key_name, "issues": issues + invalid}


def version_check(model, confirmed=None):
    return {"requested_model": model, "api_model_identifier": model.split(":", 1)[1] if model else None,
            "selection": "exact_archived_identifier" if model else "not_applicable",
            "confirmation": "operator_confirmed_identifier" if model and confirmed == model else
                            "not_confirmed" if model else "not_applicable",
            "historical_checkpoint_equivalence": "not_established" if model else "not_applicable"}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        # Never forward the reviewer's Authorization header to a redirect target.
        return None


def lookup_model(model, *, allow_network=False, environ=None):
    env = os.environ if environ is None else environ
    config = configuration(model, env)
    result = {"status": "blocked", "configuration_check": config,
              "model_version_check": version_check(model), "service_status": "not_contacted",
              "network_used": False, "response_cache_read": False, "generation_requests": 0,
              "historical_versions_reverified": False, "blockers": list(config["issues"])}
    if not model:
        result["blockers"].append("model catalogue check requires a model experiment")
    if not allow_network:
        result["blockers"].append("model catalogue check requires --allow-network")
    if result["blockers"]:
        return result
    endpoint, key, _ = _connection(model, env)
    identifier = model.split(":", 1)[1]
    url = endpoint.rstrip("/") + "/models/" + urllib.parse.quote(identifier, safe="")
    headers = {"Accept": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    request = urllib.request.Request(url, headers=headers, method="GET")
    result.update(network_used=True, checked_at_utc=datetime.now(timezone.utc).isoformat())
    try:
        # Do not implicitly forward credentials through environment-configured proxies.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        with opener.open(request, timeout=20) as response:
            body = response.read(1024 * 1024 + 1)
        if len(body) > 1024 * 1024:
            raise ValueError("oversized response")
        payload = json.loads(body)
        if not isinstance(payload, dict) or not isinstance(payload.get("id"), str):
            raise ValueError("model object required")
        status = "model_identifier_advertised" if payload["id"] == identifier else "identifier_mismatch"
    except urllib.error.HTTPError as error:
        status = {401: "authentication_rejected", 403: "authorization_rejected",
                  404: "not_found_or_lookup_unsupported", 405: "not_found_or_lookup_unsupported",
                  429: "rate_limited", 301: "redirect_rejected", 302: "redirect_rejected",
                  303: "redirect_rejected", 307: "redirect_rejected", 308: "redirect_rejected"}.get(error.code, "service_error")
        result["http_status"] = error.code
        error.close()
    except (urllib.error.URLError, TimeoutError, OSError):
        status = "unreachable"
    except (ValueError, TypeError, UnicodeError):
        status = "invalid_response"
    result.update(status=status, service_status=status)
    result["notice"] = ("The catalogue tests this endpoint's advertised identifier only, not generation access, "
                        "historical weights or output equivalence. A failed lookup does not establish retirement.")
    return result


def execution_environment(model, environ=None):
    """Allow ordinary runtime settings plus the selected provider configuration.

    This limits inherited variables; it is not a filesystem or code sandbox.
    """
    env = os.environ if environ is None else environ
    provider = model.split(":", 1)[0] if model else None
    allowed = {"openai": {"OPENAI_API_KEY", "GPT_API_KEY", "OPENAI_BASE_URL", "OPENAI_ORG_ID", "OPENAI_PROJECT_ID"},
               "custom": {"CUSTOM_API_KEY", "CUSTOM_BASE_URL", "CUSTOM_EXTRA_BODY"},
               "local": {"LOCAL_API_KEY", "LOCAL_BASE_URL", "LOCAL_EXTRA_BODY"},
               "localbase": {"LOCAL_API_KEY", "LOCAL_BASE_URL"}}.get(provider, set())
    runtime = {"PATH", "HOME", "USER", "LOGNAME", "SHELL", "TMPDIR", "TMP", "TEMP", "LANG", "TZ",
               "VIRTUAL_ENV", "CONDA_PREFIX", "CONDA_DEFAULT_ENV", "PYTHONIOENCODING", "PYTHONUTF8",
               "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH",
               "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
               "VECLIB_MAXIMUM_THREADS", "CUDA_VISIBLE_DEVICES", "MPLCONFIGDIR", "MPLBACKEND",
               "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"}
    return {name: value for name, value in env.items() if name in allowed or name in runtime or name.startswith("LC_")}
