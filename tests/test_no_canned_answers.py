"""SEZ-F01 / ADR-1: the LLM writes every answer; the only canned text is the SEC-10 template.

Behavioural: whatever the route, the answer line is the model's text verbatim or
``SAFE_FAILURE_ANSWER``. Static: code never builds a ``FinalAnswer`` itself, the safe-failure text
is defined exactly once, and no policy text is embedded in code outside the prompt module.
"""

import ast
import json

import pytest

from support_agent.agent import AgentStatics, Case, answer_case
from support_agent.config import PROJECT_ROOT, Settings
from support_agent.guards import SAFE_FAILURE_ANSWER
from support_agent.llm import FakeLLM
from support_agent.resources import Resources

SRC = PROJECT_ROOT / "src" / "support_agent"
CODE_FILES = sorted(SRC.rglob("*.py")) + [PROJECT_ROOT / "run_cases.py"]
SENTINEL = "Sentinel reply 7f3a written by the model; our support specialist team can help."


@pytest.fixture(scope="module")
def resources():
    return Resources.load(Settings.from_env({"LLM_PROVIDER": "fake"}))


@pytest.fixture(scope="module")
def statics(resources):
    return AgentStatics.build(resources)


def _final(escalation="none", policy_applied=False, cited=()):
    return {
        "final": {
            "answer": SENTINEL,
            "escalation_reason": escalation,
            "policy_applied": policy_applied,
            "cited_policies": list(cited),
        }
    }


_TOOL = {"function_call": {"name": "get_my_orders", "args": {}}}

SCENARIOS = {
    "policy": ([_final()], "How does it work?", "policy"),
    "tool": ([_TOOL, _final()], "When is my next payment?", "tool"),
    "both": ([_TOOL, _final(policy_applied=True, cited=["POL-02"])], "Can I move it?", "both"),
    "model_escalation": ([_final(escalation="other")], "Help with something odd.", "escalate"),
    "forced_hardship": ([_final()], "I lost my job.", "escalate"),
    "forced_fraud": ([_final(escalation="fraud")], "Someone hacked my account.", "escalate"),
    "forced_human": ([_final()], "Transfer me to a human agent, please.", "escalate"),
    "after_repair": ([{"text": "garbage"}, _final()], "How does it work?", "policy"),
}


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_answer_is_model_text_verbatim_on_every_route(resources, statics, name):
    script, question, route = SCENARIOS[name]
    result = answer_case(resources, FakeLLM(script), Case("n1", "u002", question), statics=statics)
    assert result.route == route
    assert result.answer == SENTINEL
    assert result.error_class is None


def test_failure_paths_use_only_the_safe_failure_template(resources, statics):
    for script in ([{"error": "bad_request"}], [{"text": "x"}, {"text": "y"}]):
        result = answer_case(
            resources, FakeLLM(script), Case("n2", "u002", "How?"), statics=statics
        )
        assert result.answer == SAFE_FAILURE_ANSWER
        assert result.route == "escalate"
        assert result.error_class is not None


def _string_constants(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]


def test_code_never_constructs_a_final_answer():
    """Only the model's JSON becomes a FinalAnswer (via validation); no module builds one."""
    offenders = []
    for path in CODE_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                if name == "FinalAnswer":
                    offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == []


def test_safe_failure_text_is_defined_once():
    fragment = "connecting you with a Sezzle"
    holders = [p.name for p in CODE_FILES if fragment in p.read_text(encoding="utf-8")]
    assert holders == ["guards.py"]


def test_no_policy_text_embedded_in_code(resources):
    """Policy sentences live in data/policies (rendered into the prompt at runtime), never in
    code: canned policy answers would have to copy them."""
    policy_lines = {
        line.strip()
        for policy in resources.policies
        for line in policy.text.splitlines()
        if len(line.strip()) >= 40
    }
    assert policy_lines
    for path in CODE_FILES:
        source = path.read_text(encoding="utf-8")
        leaked = [line for line in policy_lines if line in source]
        assert leaked == [], f"{path.name} embeds policy text: {leaked[:2]}"


def test_no_case_strings_in_code():
    """No overfitting: no golden/adversarial case question appears in code (OWN-12)."""
    questions = []
    for cases_file in sorted((PROJECT_ROOT / "cases").glob("*.jsonl")):
        for line in cases_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                questions.append(json.loads(line)["question"])
    assert questions
    for path in CODE_FILES:
        constants = _string_constants(path)
        for question in questions:
            probe = question[:40]
            assert not any(probe in c for c in constants), f"{path.name}: {probe!r}"
