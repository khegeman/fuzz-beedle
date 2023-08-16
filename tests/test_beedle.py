from woke.testing.core import default_chain

from .fuzz.beedle_flow import LenderFuzzTest


@default_chain.connect()
def test_default():
    default_chain.set_default_accounts(default_chain.accounts[0])
    import os

    Replay = int(os.getenv("WOKE_REPLAY", 0)) > 0

    if Replay:
        LenderFuzzTest.load("replay.json")
    LenderFuzzTest().run(sequences_count=1, flows_count=40)
