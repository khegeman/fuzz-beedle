from pytypes.beedle.src.utils.Structs import Pool, Borrow, Loan
from pytypes.beedle.src.Lender import Lender

from woke.development.primitive_types import bytes32, uint
from pytypes.tests.contracts.token import CERC20
from pytypes.solady.src.tokens.ERC20 import ERC20

# A lot of implementation logic is in this file
from woke.development.core import Address
from dataclasses import dataclass, asdict
from typing import Union, Literal
import math
from .state import *

REQUST_TYPES = Literal["tx", "call"]


def removeFromPool(
    account: Address,
    poolID: bytes32,
    amount: uint,
    request_type: REQUST_TYPES = "tx",
) -> uint:
    pool = get_lender().pools(poolID)
    balanceBefore = ERC20(pool.loanToken).balanceOf(account)
    print(pool)
    print(amount)
    tx = get_lender().removeFromPool(
        poolID, amount, from_=account, request_type=request_type
    )
    return ERC20(pool.loanToken).balanceOf(account) - balanceBefore


def getLoanDebt(loan: Loan, block_ts: uint) -> uint:
    timeElapsed = block_ts - loan.startTimestamp
    interest = math.floor(
        (loan.interestRate * loan.debt * timeElapsed) / 10000 / (365 * 60 * 60 * 24)
    )
    fees = math.floor((1000 * interest) / 10000)
    interest -= fees

    return loan.debt + interest + fees
