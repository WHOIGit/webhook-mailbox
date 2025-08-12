import json as _json
import ssl as _ssl
from urllib import request as _request, parse as _parse, error as _error


class RequestException(Exception):
    pass


class HTTPError(RequestException):
    def __init__(self, message, response=None):
        super().__init__(message)
        self.response = response


class Timeout(RequestException):
    pass


class _Exceptions:
    HTTPError = HTTPError
    RequestException = RequestException
    Timeout = Timeout


exceptions = _Exceptions()


def _charset_from_headers(headers):
    ctype = headers.get("Content-Type", "")
    parts = [p.strip() for p in ctype.split(";")]
    for p in parts[1:]:
        if p.lower().startswith("charset="):
            return p.split("=", 1)[1].strip()
    return "utf-8"


class Response:
    def __init__(self, url, status_code, headers, content):
        self.url = url
        self.status_code = status_code
        # Normalize header keys to standard str; urllib supplies email.message.Message-like mapping
        self.headers = {str(k): str(v) for k, v in (headers.items() if hasattr(headers, "items") else dict(headers))}
        self._content = content

    @property
    def ok(self):
        return 200 <= int(self.status_code) < 400

    @property
    def content(self):
        return self._content

    @property
    def text(self):
        try:
            return self._content.decode(_charset_from_headers(self.headers))
        except Exception:
            return self._content.decode("utf-8", errors="replace")

    def json(self):
        return _json.loads(self.text)

    def raise_for_status(self):
        if not self.ok:
            raise HTTPError(f"{self.status_code} Server Response for URL: {self.url}", response=self)


def request(method, url, params=None, data=None, json=None, headers=None, timeout=None, verify=True):
    # Build URL with query parameters
    if params:
        q = _parse.urlencode(params, doseq=True)
        url = f"{url}&{q}" if ("?" in url) else f"{url}?{q}"

    hdrs = dict(headers or {})
    body = None

    if json is not None:
        body = _json.dumps(json).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    elif isinstance(data, (bytes, bytearray)):
        body = data
    elif data is not None:
        # Treat as form data
        body = _parse.urlencode(data, doseq=True).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")

    req = _request.Request(url=url, data=body, method=method.upper(), headers=hdrs)

    # TLS verification
    context = None
    if url.lower().startswith("https"):
        if verify is False:
            context = _ssl._create_unverified_context()
        elif isinstance(verify, str):
            context = _ssl.create_default_context(cafile=verify)
        else:
            context = None

    try:
        with _request.urlopen(req, timeout=timeout, context=context) as resp:
            status = resp.getcode()
            headers = resp.headers
            content = resp.read()
            return Response(url, status, headers, content)
    except _error.HTTPError as e:
        # Do not raise here; align with requests semantics (only raise on raise_for_status)
        status = getattr(e, "code", 0)
        headers = getattr(e, "headers", {})
        try:
            content = e.read()
        except Exception:
            content = b""
        return Response(url, status, headers, content)
    except _error.URLError as e:
        msg = str(e.reason) if getattr(e, "reason", None) else str(e)
        if "timed out" in msg.lower():
            raise Timeout(msg) from e
        raise RequestException(msg) from e


def get(url, params=None, **kwargs):
    return request("GET", url, params=params, **kwargs)


def post(url, data=None, json=None, **kwargs):
    return request("POST", url, data=data, json=json, **kwargs)


def put(url, data=None, json=None, **kwargs):
    return request("PUT", url, data=data, json=json, **kwargs)


def delete(url, **kwargs):
    return request("DELETE", url, **kwargs)


def head(url, **kwargs):
    return request("HEAD", url, **kwargs)