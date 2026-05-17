// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// Foundry scaffold (default). Import forge-std/Test.sol; extend Test.
// For Hardhat, see the comment at the bottom of this file.
// Replace MyContract and placeholder values with real names.
// Run: forge test --match-contract ExampleTest -vvv

import {Test, console} from "forge-std/Test.sol";
import {MyContract} from "../src/MyContract.sol";

contract ExampleTest is Test {
    MyContract public myContract;
    address public constant OWNER = address(0x1);

    function setUp() public {
        vm.prank(OWNER);
        myContract = new MyContract();
    }

    function test_doSomethingReturnsExpectedValue() public {
        uint256 result = myContract.doSomething(42);
        assertEq(result, 84, "expected double the input");
    }

    function test_doSomethingRevertsForZeroInput() public {
        vm.expectRevert("input must be nonzero");
        myContract.doSomething(0);
    }

    function test_ownerCanCallPrivilegedFunction() public {
        vm.prank(OWNER);
        myContract.privilegedAction();
        assertTrue(myContract.actionExecuted());
    }
}

// --- Hardhat alternative (JavaScript) ---
// If the project uses Hardhat, create test/ExampleTest.js instead:
//
// const { expect } = require("chai");
// const { ethers } = require("hardhat");
//
// describe("MyContract", function () {
//   it("doSomething returns double the input", async function () {
//     const MyContract = await ethers.getContractFactory("MyContract");
//     const contract = await MyContract.deploy();
//     expect(await contract.doSomething(42)).to.equal(84);
//   });
// });
