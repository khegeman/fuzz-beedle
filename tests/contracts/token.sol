pragma solidity ^0.8.13;
import {ERC20} from "solady/src/tokens/ERC20.sol";


contract CERC20 is ERC20 {
    string public _name;
    string public _symbol;

    constructor(string memory n, string memory s) public {
        _name=n;
        _symbol=s;
    }
    
    function name() public view override returns (string memory) {
        return _name;
    }

    function symbol() public view override returns (string memory) {
        return _symbol;
    }

    function mint(address _to, uint256 _amount) public {
        _mint(_to, _amount);
    }
}

contract LERC20 is ERC20 {

    function name() public pure override returns (string memory) {
        return "Loan ERC20";
    }

    function symbol() public pure override returns (string memory) {
        return "LERC20";
    }

    function mint(address _to, uint256 _amount) public {
        _mint(_to, _amount);
    }
}