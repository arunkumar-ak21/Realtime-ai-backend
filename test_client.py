import asyncio
import websockets
import sys

# Windows Helper for asyncio policy (prevent event loop closed errors on exit)
if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def chat():
    # Use a arbitrary session ID for testing (Must be UUID)
    session_id = "550e8400-e29b-41d4-a716-446655440000"
    uri = f"ws://localhost:8000/ws/session/{session_id}"
    
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected! Type your message (or 'quit' to exit):")
            
            while True:
                user_input = input("You: ")
                if user_input.lower() in ['quit', 'exit']:
                    break
                
                await websocket.send(user_input)
                
                print("AI: ", end="", flush=True)
                
                # Simple logic: assume we keep receiving message parts until... actually WebSocket is continuous stream.
                # In this simple client, we just listen for a bit or until we deem response 'complete' 
                # but server doesn't send "End of Turn".
                # For this demo, we'll listen for one giant generic receive loop isn't perfect for "User Input -> Response" lockstep without a protocol.
                # HACK: We'll wait for messages with a timeout to detect "silence" as end of turn.
                
                try:
                    while True:
                        response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                        print(response, end="", flush=True)
                except asyncio.TimeoutError:
                    # Assume turn done
                    print("\n")
                    
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(chat())
    except KeyboardInterrupt:
        print("\nExiting...")
