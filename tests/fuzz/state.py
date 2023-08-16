# state for the fuzz test

from woke.development.core import Account

from woke.testing.core import default_chain
from woke.development.primitive_types import uint, bytes32
from typing import List
from wokelib.generators.random import st
from pytypes.beedle.src.Lender import Lender
from pytypes.beedle.src.utils.Structs import Pool, Loan


from pytypes.solady.src.tokens.ERC20 import ERC20

from pytypes.tests.contracts.token import CERC20
from eth_utils.currency import to_wei

from dataclasses import dataclass

from wokelib import Mirror

import math


@dataclass
class GiveLoan:
    loan_id: uint
    pool_id: bytes32


_users = list()
_tokens = list()

_pool_mirror = Mirror()
_loan_mirror = Mirror()

_lender = None
_owner: Account

_last_debt = {}


def users() -> List[Account]:
    global _users
    return _users


def tokens() -> List[ERC20]:
    global _tokens
    return _tokens


def get_lender() -> Lender:
    global _lender
    if _lender is None:
        raise
    return _lender


def set_lender(l: Lender):
    global _lender
    _lender = l


def owner() -> Account:
    global _owner
    return _owner


def pool_mirror() -> Mirror:
    global _pool_mirror
    return _pool_mirror


def loan_mirror() -> Mirror:
    global _loan_mirror
    return _loan_mirror


def PoolCount():
    return len(pool_mirror())


def LoanCount():
    return len(loan_mirror())


def update_loan(loan_id: uint):
    l: Loan = get_lender().loans(loan_id)
    if l.debt == 0:
        loan_mirror().delete_key(loan_id)
    else:
        loan_mirror()[loan_id] = l


def update_pool(pool_id: bytes32):
    ##update our local cache of pool data
    pool: Pool = get_lender().pools(pool_id)
    pool_mirror()[pool_id] = pool


def get_last_debt(loan_id: uint) -> uint:
    global _last_debt
    return _last_debt.get(loan_id, 0)


def set_last_debt(loan_id: uint, debt: uint):
    global _last_debt
    _last_debt[loan_id] = debt


def initialize(token_count: int):
    global _owner
    global _last_debt
    global _pool_mirror

    tokenCount = 2
    _owner = default_chain.accounts[0]
    _last_debt.clear()
    set_lender(Lender.deploy(from_=_owner))

    _pool_mirror.bind(get_lender().pools)
    _loan_mirror.bind(get_lender().loans)

    users().clear()
    for u in default_chain.accounts[1:5]:
        users().append(u)

    tokens().clear()
    for t in [CERC20.deploy(f"T{i}", "T{i}") for i in range(0, tokenCount)]:
        tokens().append(t)
        t.approve(get_lender(), st.MAX_UINT, from_=_owner)
        t.mint(_owner, to_wei(1000, "ether"), from_=_owner)
        for u in users():
            t.mint(u, to_wei(10, "ether"), from_=_owner)

    print([t.name() for t in tokens()])
