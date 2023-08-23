from woke.testing.core import default_chain

from .fuzz.beedle_flow import LenderFuzzTest


@default_chain.connect()
def test_default():
    default_chain.set_default_accounts(default_chain.accounts[0])
    import os

    Replay = os.getenv("WOKE_REPLAY", None)

    if Replay is not None:
        LenderFuzzTest.load(Replay)
    LenderFuzzTest().run(sequences_count=1, flows_count=30, record=True)
