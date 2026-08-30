#!/usr/bin/env python3
"""
Simple WebSocket test client.
Tests connection, ping/pong, and task streaming.
"""
import asyncio
import json
import sys
from datetime import datetime

try:
    import websockets
except ImportError:
    print("Error: websockets library not installed")
    print("Run: pip install websockets")
    sys.exit(1)


async def test_websocket():
    """Test WebSocket connection and basic functionality."""
    uri = "ws://localhost:8000/ws"
    
    print(f"🔌 Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected!")
            
            # Wait for connection confirmation
            message = await websocket.recv()
            data = json.loads(message)
            print(f"\n📨 Received: {data['type']}")
            if data['type'] == 'connected':
                print(f"   Connection ID: {data['connectionId']}")
            
            # Test ping/pong
            print("\n🏓 Testing ping/pong...")
            await websocket.send(json.dumps({"type": "ping"}))
            message = await websocket.recv()
            data = json.loads(message)
            if data['type'] == 'pong':
                print("✅ Pong received!")
            
            # Test task submission
            print("\n📤 Sending test task...")
            task = {
                "type": "task",
                "task": {
                    "message": "Hello, can you help me understand how AI agents collaborate?",
                    "enableCollaboration": True,
                    "maxSubAgents": 2
                }
            }
            
            await websocket.send(json.dumps(task))
            print("✅ Task sent! Waiting for events...")
            
            # Receive and display events
            event_count = 0
            max_events = 20  # Limit for testing
            
            print("\n" + "="*60)
            print("STREAMING EVENTS:")
            print("="*60)
            
            while event_count < max_events:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    data = json.loads(message)
                    event_count += 1
                    
                    event_type = data.get('type', 'unknown')
                    
                    # Display different event types
                    if event_type == 'init':
                        print(f"\n🎬 [{event_count}] INIT - Conversation {data.get('conversationId', 'N/A')}")
                    
                    elif event_type == 'agent_status':
                        agent_id = data.get('agentId', 'unknown')
                        status = data.get('status', 'unknown')
                        msg = data.get('message', '')
                        print(f"\n🤖 [{event_count}] AGENT STATUS - {agent_id}")
                        print(f"   Status: {status}")
                        if msg:
                            print(f"   Message: {msg}")
                    
                    elif event_type == 'delegation':
                        agents = data.get('subAgents', [])
                        print(f"\n👥 [{event_count}] DELEGATION - {len(agents)} agents")
                        for query in data.get('queries', []):
                            print(f"   - {query.get('agentType')}: {query.get('query')[:50]}...")
                    
                    elif event_type == 'agent_thinking':
                        agent_type = data.get('agentType', 'unknown')
                        round_num = data.get('roundNumber', 0)
                        print(f"\n💭 [{event_count}] THINKING - {agent_type} (Round {round_num})")
                    
                    elif event_type == 'agent_message_chunk':
                        # Real-time streaming chunk
                        content = data.get('content', '')
                        print(content, end='', flush=True)
                    
                    elif event_type == 'agent_message':
                        agent_type = data.get('agentType', 'unknown')
                        round_num = data.get('roundNumber', 0)
                        is_complete = data.get('isComplete', False)
                        if is_complete:
                            print(f"\n\n✅ [{event_count}] MESSAGE COMPLETE - {agent_type} (Round {round_num})")
                    
                    elif event_type == 'stream':
                        content = data.get('content', '')
                        is_final = data.get('isFinal', False)
                        if not is_final:
                            print(content, end='', flush=True)
                        else:
                            print("\n")
                    
                    elif event_type == 'complete':
                        print(f"\n\n🎉 [{event_count}] TASK COMPLETE!")
                        print(f"   Conversation ID: {data.get('conversationId', 'N/A')}")
                        break
                    
                    elif event_type == 'error':
                        print(f"\n\n❌ [{event_count}] ERROR: {data.get('error', 'Unknown error')}")
                        break
                    
                    elif event_type == 'conversation_round_complete':
                        round_num = data.get('roundNumber', 0)
                        msg_count = data.get('messageCount', 0)
                        print(f"\n\n🔄 [{event_count}] ROUND {round_num} COMPLETE - {msg_count} messages")
                    
                    else:
                        print(f"\n📦 [{event_count}] {event_type.upper()}")
                
                except asyncio.TimeoutError:
                    print("\n⏰ Timeout waiting for events")
                    break
            
            print("\n" + "="*60)
            print(f"Test complete! Received {event_count} events")
            print("="*60)
    
    except websockets.exceptions.WebSocketException as e:
        print(f"❌ WebSocket error: {e}")
        sys.exit(1)
    except ConnectionRefusedError:
        print("❌ Connection refused - is the backend running?")
        print("   Start it with: cd backend && python main.py")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    print("🧪 WebSocket Test Client")
    print("=" * 60)
    print()
    
    try:
        asyncio.run(test_websocket())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(0)

