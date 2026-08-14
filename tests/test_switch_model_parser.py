from unittest.mock import patch

from app.agent.switch_model_parser import SwitchModelRegistry, parse_switch_models
from app.main import _load_switch_models_json


def test_registry_keeps_a_switch_model_without_specifications():
    registry = SwitchModelRegistry()

    registry.add_many([{"model_name": "NetEngine 8000 M14"}])

    assert registry.to_list() == [{"model_name": "NetEngine 8000 M14"}]


def test_parser_requires_the_selected_node_title_as_the_model_name():
    with patch("app.agent.switch_model_parser.get_llm") as get_llm:
        get_llm.return_value.complete.return_value.text = "{}"

        parse_switch_models("PDF facts", "NetEngine 8000 M4")

    request = get_llm.return_value.complete.call_args.args[0]
    assert "copy the supplied selected switch-model node title exactly" in request
    assert "Selected switch-model node title: NetEngine 8000 M4" in request


def test_loader_recovers_json_from_a_fenced_code_snippet():
    assert _load_switch_models_json('```json\n{"model_name": "NetEngine 8000 M14"}\n```') == [
        {"model_name": "NetEngine 8000 M14"}
    ]
