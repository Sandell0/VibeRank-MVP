from __future__ import annotations

import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .clients import ProviderError
from .evaluation import EvaluationConfig, run_evaluation, run_synthetic_validation, runtime_config
from .leaderboard import DEFAULT_IRT_URL, fetch_known_models, select_known_models


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"


class VibeRankHandler(BaseHTTPRequestHandler):
    server_version = "VibeRank/0.1"

    def _json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path == "/" else request_path.lstrip("/")
        target = (WEB_ROOT / relative).resolve()
        if WEB_ROOT.resolve() not in target.parents and target != WEB_ROOT.resolve():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = target.read_bytes()
        content_type, _ = mimetypes.guess_type(target.name)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type or 'application/octet-stream'}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/health":
            self._json({"status": "ok"})
        elif path == "/api/config":
            self._json(runtime_config())
        elif path == "/api/leaderboard-models":
            try:
                query = parse_qs(parsed.query)
                limit = int(query.get("limit", ["200"])[0])
                minimum_benchmarks = int(query.get("minimum_benchmarks", ["5"])[0])
                models = select_known_models(
                    fetch_known_models(),
                    limit=limit,
                    minimum_benchmarks=minimum_benchmarks,
                )
                self._json(
                    {
                        "source": DEFAULT_IRT_URL,
                        "models": [model.to_dict() for model in models],
                    }
                )
            except (ValueError, RuntimeError) as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)
        else:
            self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            payload = self._read_json()
            if path == "/api/evaluate":
                config = EvaluationConfig(
                    provider=str(payload.get("provider", "simulation")),
                    model=str(payload.get("model", "simulated-model")),
                    questions=int(payload.get("questions", 3)),
                    target_elo=(
                        float(payload["target_elo"])
                        if payload.get("target_elo") is not None
                        else None
                    ),
                    seed=int(payload.get("seed", 7)),
                    question_mode=(
                        str(payload["question_mode"])
                        if payload.get("question_mode") is not None
                        else None
                    ),
                )
                self._json(run_evaluation(config))
            elif path == "/api/validate":
                self._json(
                    run_synthetic_validation(
                        questions=int(payload.get("questions", 3)),
                        repeats=int(payload.get("repeats", 20)),
                        seed=int(payload.get("seed", 17)),
                        question_mode=(
                            str(payload["question_mode"])
                            if payload.get("question_mode") is not None
                            else None
                        ),
                    )
                )
            else:
                self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except (ValueError, json.JSONDecodeError, ProviderError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover - final API safety net
            self._json({"error": f"Unexpected server error: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[viberank] {self.address_string()} - {format % args}")


def main() -> None:
    host = os.environ.get("VIBERANK_HOST", "127.0.0.1")
    port = int(os.environ.get("VIBERANK_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), VibeRankHandler)
    print(f"VibeRank running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
