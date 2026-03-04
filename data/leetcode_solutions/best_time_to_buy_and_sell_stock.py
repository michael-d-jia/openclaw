"""
Best Time to Buy and Sell Stock
Topic: Arrays
Description:
You are given an array prices where prices[i] is the price of a given stock on the ith day.

You want to maximize your profit by choosing a single day to buy one stock and choosing a different day in the future to sell that stock.

Return the maximum profit you can achieve from this transaction. If you cannot achieve any profit, return 0.

 
Example 1:


Input: prices = [7,1,5,3,6,4]
Output: 5
Explanation: Buy on day 2 (price = 1) and sell on day 5 (price = 6), profit = 6-1 = 5.
Note that buying on day 2 and selling on day 1 is not allowed because you must buy before you sell.


Example 2:


Input: prices = [7,6,4,3,1]
Output: 0
Explanation: In this case, no transactions are done and the max profit = 0.


 
Constraints:


	1 <= prices.length <= 105
	0 <= prices[i] <= 104
"""

def maxProfit(prices: list[int]) -> int:
    pass

if __name__ == "__main__":
    # Test cases
    # Example 1
    assert maxProfit([7,1,5,3,6,4]) == 5, f"Test Case 1 Failed: Expected 5, Got {maxProfit([7,1,5,3,6,4])}"
    # Example 2
    assert maxProfit([7,6,4,3,1]) == 0, f"Test Case 2 Failed: Expected 0, Got {maxProfit([7,6,4,3,1])}"
    # Additional test case: Simple increasing prices
    assert maxProfit([1,2]) == 1, f"Test Case 3 Failed: Expected 1, Got {maxProfit([1,2])}"
    # Additional test case: Simple decreasing prices
    assert maxProfit([2,1]) == 0, f"Test Case 4 Failed: Expected 0, Got {maxProfit([2,1])}"
    # Additional test case: Single element array (no transaction possible)
    assert maxProfit([1]) == 0, f"Test Case 5 Failed: Expected 0, Got {maxProfit([1])}"

    print("All test cases passed!")