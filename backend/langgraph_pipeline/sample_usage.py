# from langchain_core.messages import HumanMessage
# from workflows import create_multi_turn_workflow

# def run_query(query: str):
#     """Run a simple query through the workflow."""
#     app = create_multi_turn_workflow()
    
#     result = app.invoke({
#         "messages": [HumanMessage(content=query)]
#     })
    
#     print(f"Query: {query}")
#     print("-" * 40)
#     for msg in result['messages']:
#         print(f"{type(msg).__name__}: {msg.content}")
    
#     return result

# if __name__ == "__main__":
#     # Test queries
#     run_query("What's the weather in New York today?")
#     print("\n" + "="*50 + "\n")
#     run_query("Get weather for New York today and yesterday, then calculate the difference")



from langchain_core.messages import HumanMessage, AIMessage
from workflows import create_multi_turn_workflow, create_streaming_workflow
import time

def run_query(query: str):
    """Run a simple query through the workflow."""
    app = create_multi_turn_workflow()
    
    result = app.invoke({
        "messages": [HumanMessage(content=query)]
    })
    
    print(f"Query: {query}")
    print("-" * 40)
    for msg in result['messages']:
        print(f"{type(msg).__name__}: {msg.content}")
    
    return result

def run_streaming_query(query: str):
    """Run a query with streaming response."""
    app = create_streaming_workflow()
    
    inputs = {"messages": [HumanMessage(content=query)]}
    
    print(f"Query: {query}")
    print("-" * 40)
    print("Streaming Response:")
    print("-" * 20)
    
    # Stream the workflow execution
    for chunk in app.stream(inputs):
        for node_name, node_output in chunk.items():
            print(f"\n[{node_name.upper()}]:")
            
            if 'messages' in node_output:
                for message in node_output['messages']:
                    if isinstance(message, AIMessage):
                        if hasattr(message, 'tool_calls') and message.tool_calls:
                            print(f"🔧 Making {len(message.tool_calls)} tool call(s):")
                            for tool_call in message.tool_calls:
                                print(f"   - {tool_call['name']} with args: {tool_call['args']}")
                        else:
                            print(f"🤖 Assistant: {message.content}")
                    else:
                        print(f"📝 {type(message).__name__}: {message.content}")
            
            print("-" * 20)
            time.sleep(0.1)  # Small delay to show streaming effect
    
    print("\n✅ Streaming complete!")

def run_streaming_with_events(query: str):
    """Run a query with detailed streaming events."""
    app = create_streaming_workflow()
    
    inputs = {"messages": [HumanMessage(content=query)]}
    
    print(f"Query: {query}")
    print("=" * 50)
    
    # Stream with events for more detailed output
    for event in app.stream(inputs, stream_mode="values"):
        messages = event.get('messages', [])
        if messages:
            last_message = messages[-1]
            if isinstance(last_message, AIMessage):
                if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                    print(f"🔧 Tool calls detected: {len(last_message.tool_calls)}")
                    for i, tool_call in enumerate(last_message.tool_calls, 1):
                        print(f"   {i}. {tool_call['name']} → {tool_call['args']}")
                elif last_message.content:
                    print(f"🤖 Final Response: {last_message.content}")
        print("-" * 30)

def run_token_streaming_query(query: str):
    """Run a query with token-by-token streaming (simulated)."""
    app = create_streaming_workflow()
    
    inputs = {"messages": [HumanMessage(content=query)]}
    
    print(f"Query: {query}")
    print("-" * 40)
    print("Token-by-token streaming:")
    print("-" * 25)
    
    final_response = ""
    
    for chunk in app.stream(inputs):
        for node_name, node_output in chunk.items():
            if node_name == "agent" and 'messages' in node_output:
                for message in node_output['messages']:
                    if isinstance(message, AIMessage) and message.content:
                        if not hasattr(message, 'tool_calls') or not message.tool_calls:
                            # Simulate token streaming for final response
                            response_text = message.content
                            if response_text != final_response:
                                new_tokens = response_text[len(final_response):]
                                for token in new_tokens.split():
                                    print(f"{token} ", end="", flush=True)
                                    time.sleep(0.1)  # Simulate streaming delay
                                final_response = response_text
                                print()  # New line after complete response
            elif node_name == "tools":
                print(f"\n🔧 [TOOLS EXECUTING...]")
                time.sleep(0.3)  # Simulate tool execution time
    
    print("\n✅ Streaming complete!")

if __name__ == "__main__":
    
    print("\n\n=== STREAMING QUERY ===")
    run_streaming_query("What's the weather in New York today? add this with yesterday's weather, return the sum of both, return teh word 'tool' in response also")
    