import pytest
from apps.motor_response.router import decide_playbook
from apps.motor_response.schemas import Signals, SalesState

@pytest.fixture
def empty_state():
    return SalesState()

@pytest.fixture
def signals_base():
    return Signals(intent="GENERAL", risk=False, objection=None)

def test_router_priority_1_risk(empty_state, signals_base):
    """El riesgo debe ganar a todo."""
    signals = signals_base.copy()
    signals.risk = True
    # Incluso con ventana cerrada o handoff pedido, risk gana (o empata en nivel, pero checkeamos primero)
    decision = decide_playbook(signals, empty_state, window_open=True)
    assert decision.playbook_key == "SAFE_BOUNDARY"
    assert decision.priority_level == 1

def test_router_priority_2_window_closed(empty_state, signals_base):
    """Ventana cerrada fuerza reapertura."""
    decision = decide_playbook(signals_base, empty_state, window_open=False)
    assert decision.playbook_key == "REOPEN_24H"
    assert decision.priority_level == 1

def test_router_priority_3_handoff(empty_state, signals_base):
    """Pedido explícito de humano."""
    signals = signals_base.copy()
    signals.intent = "HANDOFF_REQUEST"
    decision = decide_playbook(signals, empty_state, window_open=True)
    assert decision.playbook_key == "HANDOFF"
    assert decision.priority_level == 2

def test_router_priority_4_objection_price(empty_state, signals_base):
    """Objeción de precio."""
    signals = signals_base.copy()
    signals.objection = "PRICE_TOO_HIGH"
    decision = decide_playbook(signals, empty_state, window_open=True)
    assert decision.playbook_key == "OBJECTION_PRICE"
    assert decision.priority_level == 3

def test_router_priority_5_intent_explicit(empty_state, signals_base):
    """Intención clara de compra."""
    signals = signals_base.copy()
    signals.intent = "ASK_PRICE"
    decision = decide_playbook(signals, empty_state, window_open=True)
    assert decision.playbook_key == "PRICE_QUOTE_MIN"
    assert decision.priority_level == 4

def test_router_priority_6_missing_info(empty_state, signals_base):
    """Faltantes críticos (proactividad)."""
    state = empty_state.copy()
    state.missing = ["model"]
    decision = decide_playbook(signals_base, state, window_open=True)
    assert decision.playbook_key == "DISCOVERY_MIN"
    assert decision.priority_level == 5

def test_router_default(empty_state, signals_base):
    """Nada activado -> Default."""
    decision = decide_playbook(signals_base, empty_state, window_open=True)
    assert decision.playbook_key == "DEFAULT_ASSIST"
    assert decision.priority_level == 6
