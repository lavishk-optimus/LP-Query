from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
# from agents.sql_agent import create_sql_agent_name
from datetime import datetime

@tool
def get_weather(location: str, date: str = "today") -> str:
    """Get weather information for a specific location and date."""
    weather_data = {
        ("today", "new york"): "Temperature: 22°C, Sunny",
        ("yesterday", "new york"): "Temperature: 18°C, Cloudy",
        ("today", "london"): "Temperature: 15°C, Rainy",
        ("yesterday", "london"): "Temperature: 12°C, Foggy"
    }
    key = (date.lower(), location.lower())
    return weather_data.get(key, f"Weather data not available for {location} on {date}")

@tool
def calculator(expression: str) -> str:
    """Perform mathematical calculations."""
    try:
        allowed_chars = set('0123456789+-*/.() ')
        if all(c in allowed_chars for c in expression):
            result = eval(expression)
            return f"Result: {result}"
        else:
            return "Error: Invalid characters in expression"
    except Exception as e:
        return f"Error calculating: {str(e)}"

@tool
def search_web(query: str) -> str:
    """Search the web for information."""
    return f"Search results for '{query}': Here are some relevant results..."

@tool
def get_current_time() -> str:
    """Get the current date and time."""
    return f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"



# @tool
# def sql_tool(query: str) -> str:
    data=  [{
    "Fund Name": "Harbor Growth Fund III",
    "Vintage": 2017,
    "Commitment": "$5,000,000",
    "Paid-In": "$4,250,000",
    "NAV": "$6,300,000",
    "Net IRR": "18.2%",
    "DPI": "0.68x",
    "TVPI": "1.63x",
    "PME vs Index": "+3.4%",
    "Unfunded": "$750,000",
    "Status": "Mature",
    "Last Reported": "2025-06-30"
  },
  {
    "Fund Name": "Meridian Opportunities Fund IV",
    "Vintage": 2020,
    "Commitment": "$3,000,000",
    "Paid-In": "$2,250,000",
    "NAV": "$2,950,000",
    "Net IRR": "13.0%",
    "DPI": "0.35x",
    "TVPI": "1.42x",
    "PME vs Index": "+1.4%",
    "Unfunded": "$750,000",
    "Status": "Active",
    "Last Reported": "2025-06-30"
  },
  {
    "Fund Name": "Keystone Venture II",
    "Vintage": 2015,
    "Commitment": "$2,500,000",
    "Paid-In": "$2,500,000",
    "NAV": "$1,850,000",
    "Net IRR": "8.9%",
    "DPI": "0.97x",
    "TVPI": "1.52x",
    "PME vs Index": "−0.6%",
    "Unfunded": "$0",
    "Status": "Exited",
    "Last Reported": "2025-06-30"
  },
  {
    "Fund Name": "Summit Innovation Fund I",
    "Vintage": 2021,
    "Commitment": "$4,000,000",
    "Paid-In": "$2,800,000",
    "NAV": "$3,950,000",
    "Net IRR": "15.4%",
    "DPI": "0.25x",
    "TVPI": "1.50x",
    "PME vs Index": "+2.0%",
    "Unfunded": "$1,200,000",
    "Status": "Active",
    "Last Reported": "2025-06-30"
  },
  {
    "Fund Name": "Atlas Digital Fund II",
    "Vintage": 2018,
    "Commitment": "$6,500,000",
    "Paid-In": "$5,700,000",
    "NAV": "$7,900,000",
    "Net IRR": "19.6%",
    "DPI": "0.70x",
    "TVPI": "1.58x",
    "PME vs Index": "+3.7%",
    "Unfunded": "$800,000",
    "Status": "Mature",
    "Last Reported": "2025-06-30"
  },
  {
    "Fund Name": "Horizon Ventures Fund V",
    "Vintage": 2022,
    "Commitment": "$4,500,000",
    "Paid-In": "$3,000,000",
    "NAV": "$3,600,000",
    "Net IRR": "11.8%",
    "DPI": "0.20x",
    "TVPI": "1.33x",
    "PME vs Index": "+1.2%",
    "Unfunded": "$1,500,000",
    "Status": "Active",
    "Last Reported": "2025-06-30"
  },
  {
    "Fund Name": "NorthPeak Growth Fund IV",
    "Vintage": 2016,
    "Commitment": "$5,200,000",
    "Paid-In": "$5,000,000",
    "NAV": "$6,400,000",
    "Net IRR": "16.1%",
    "DPI": "0.88x",
    "TVPI": "1.56x",
    "PME vs Index": "+2.5%",
    "Unfunded": "$200,000",
    "Status": "Mature",
    "Last Reported": "2025-06-30"
  },
  {
    "Fund Name": "Stellar Impact Fund I",
    "Vintage": 2019,
    "Commitment": "$3,800,000",
    "Paid-In": "$3,300,000",
    "NAV": "$4,250,000",
    "Net IRR": "14.9%",
    "DPI": "0.60x",
    "TVPI": "1.51x",
    "PME vs Index": "+2.9%",
    "Unfunded": "$500,000",
    "Status": "Active",
    "Last Reported": "2025-06-30"
  },
  {
    "Fund Name": "Crescent Equity Partners III",
    "Vintage": 2014,
    "Commitment": "$6,000,000",
    "Paid-In": "$6,000,000",
    "NAV": "$6,900,000",
    "Net IRR": "10.3%",
    "DPI": "1.10x",
    "TVPI": "1.53x",
    "PME vs Index": "+0.5%",
    "Unfunded": "$0",
    "Status": "Exited",
    "Last Reported": "2025-06-30" },
  {    "Fund Name": "Apex Venture Growth II",
    "Vintage": 2023,
    "Commitment": "$5,500,000",
    "Paid-In": "$2,400,000",
    "NAV": "$2,900,000",
    "Net IRR": "9.7%",
    "DPI": "0.10x",
    "TVPI": "1.21x",
    "PME vs Index": "+0.8%",
    "Unfunded": "$3,100,000",
    "Status": "Active",
    "Last Reported": "2025-06-30"}]
    """Execute SQL query on the dataset."""

    cont="""

data is {data}, the query is {query}.

"""

    a=create_sql_agent_name()

    agent_resp=a.invoke([HumanMessage(content=cont)])


    final_resp=agent_resp.content

    return final_resp

    # include all the tools here, which need to be used in the agents or workflows
ALL_TOOLS = [get_weather, calculator, search_web, get_current_time]