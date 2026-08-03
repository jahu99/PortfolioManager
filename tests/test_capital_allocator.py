import pandas as pd

from analysis.capital_allocator import generate_capital_allocation



portfolio = pd.DataFrame([

{
"Ticker":"NVDA",
"Sector":"Technology",
"Current Value":50000,
"Investment Score":90
},

{
"Ticker":"MSFT",
"Sector":"Technology",
"Current Value":5000,
"Investment Score":80
},

{
"Ticker":"AAPL",
"Sector":"Technology",
"Current Value":3000,
"Investment Score":75
}

])



rankings = pd.DataFrame([

{
"Ticker":"CARE",
"Sector":"Financial Services",
"Investment Score":100,
"Quality Score":67,
"Signal":"STRONG BUY",
"Confidence":"High"
},

{
"Ticker":"DXCM",
"Sector":"Healthcare",
"Investment Score":95,
"Quality Score":46,
"Signal":"BUY",
"Confidence":"Medium"
}

])



sector = pd.DataFrame([

{
"Sector":"Financial Services",
"Action":"ADD"
}

])



result = generate_capital_allocation(

portfolio,

rankings,

sector

)


print("\n--- PORTFOLIO DECISION TEST ---")


print("\nBUY")

for x in result["BUY"]:
    print(x)


print("\nREDUCE")

for x in result["REDUCE"]:
    print(x)


print("\nAVOID")

for x in result["AVOID"]:
    print(x)


print("\nCash Remaining")

print(result["Cash Remaining"])