# WebSocket Connection Fixes

## Issues Fixed

### ✅ Issue 1: Error 31941 - Invalid Track Configuration
**Problem**: TwiML was using `track="inbound_track outbound_track"` which is invalid syntax for the `<Connect>` verb.

**Fix**: Changed to `track="inbound_track"` as per [Twilio Error 31941](https://www.twilio.com/docs/api/errors/31941).

**File**: `concierge/server.py` line 166

### ✅ Issue 2: WebSocket Query Parameter Handling  
**Problem**: Using FastAPI's `Query(...)` parameter validation on WebSocket endpoints can cause handshake failures.

**Fix**: Changed to manual query parameter extraction using `websocket.query_params` which is more compatible with WebSocket connections.

**File**: `concierge/server.py` lines 291-335

### ✅ Issue 3: Error Handling
**Problem**: Exceptions before `websocket.accept()` could prevent proper WebSocket handshake.

**Fix**: Added comprehensive try-catch around the accept() call with graceful error handling.

**File**: `concierge/server.py` lines 307-329

## Current Issue: Error 31920 - WebSocket Handshake Error

**Error**: [Twilio Error 31920](https://www.twilio.com/docs/api/errors/31920) - "The server has returned an HTTP code different from 101"

**Meaning**: Twilio IS attempting to connect to the WebSocket, but not receiving the expected HTTP 101 (Switching Protocols) response.

**Progress**: ✅ Twilio now tries to connect (previous error 31941 fixed)
              ❌ Handshake still failing

## Testing Steps

### Step 1: Restart Server
```bash
python -m concierge.server
```

### Step 2: Test /media-stream Endpoint Manually

Open `tests/test_media_stream.html` in your browser:
1. Enter a test call ID (e.g., "test-call-123")
2. Click "Test /media-stream Connection"
3. Check if WebSocket connects successfully

**Expected Result:**
- ✅ "WebSocket connected to /media-stream!"
- Check server logs for the detailed connection info

**If this works**, the endpoint is fine and the issue is specific to Twilio's connection attempt.

**If this fails**, we have a server-side issue to fix.

### Step 3: Check Server Logs

When testing, look for:
```
======================================================================
🔌 MEDIA STREAM WebSocket connection attempt
  Call ID: test-call-123
  Client: ...
  Query params: {'call_id': 'test-call-123'}
  Headers: {...}
======================================================================
✓✓✓ WebSocket ACCEPTED for call test-call-123
```

### Step 4: Make Real Test Call

```bash
python -m concierge.cli
```

Make a reservation request and watch for:
1. Server logs showing WebSocket connection attempt
2. No Error 31920 in Twilio logs
3. Successful audio streaming

### Step 5: Check ngrok Logs

In ngrok web interface (http://127.0.0.1:4040), look for:
- WebSocket upgrade requests to `/media-stream`
- HTTP status codes returned (should be 101)
- Any errors or failed requests

## Debugging Checklist

- [ ] Server restarted with latest code
- [ ] `/ws-test` endpoint works (confirmed WebSocket support)
- [ ] `/media-stream` endpoint tested with test_media_stream.html
- [ ] ngrok shows WebSocket upgrade requests
- [ ] Server logs show connection attempts
- [ ] Twilio logs checked for errors
- [ ] Call connects and stays connected

## Potential Remaining Issues

If error 31920 persists after fixes:

### 1. ngrok WebSocket Path Issue
Some ngrok configurations might have issues with query parameters on WebSocket URLs.

**Test**: Try connecting without query parameter first to isolate the issue.

### 2. Timing Issue
The WebSocket connection might be timing out before Twilio can complete the handshake.

**Solution**: Already added fast accept() - should not be an issue.

### 3. Server Response Issue
Something between the client and our server is intercepting the response.

**Debug**: Check ngrok logs to see what's being returned.

### 4. Twilio-Specific Headers
Twilio might require specific headers that we're not handling.

**Debug**: Log all headers from Twilio's connection attempt and compare with browser test.

## Next Steps

1. **Test the endpoint manually** using `test_media_stream.html`
2. **Check server logs** for detailed connection info
3. **Make a test call** and observe both server and Twilio logs
4. **Compare headers** between browser test and Twilio connection
5. **Check ngrok dashboard** for WebSocket requests

## Files Changed

- `concierge/server.py` - Fixed TwiML and WebSocket handling
- `tests/test_media_stream.html` - New test page for manual verification
- `WEBSOCKET_FIXES.md` - This documentation

## Resources

- [Twilio Error 31920](https://www.twilio.com/docs/api/errors/31920)
- [Twilio Error 31941](https://www.twilio.com/docs/api/errors/31941)
- [Twilio Media Streams](https://www.twilio.com/docs/voice/twiml/stream)
- [FastAPI WebSocket](https://fastapi.tiangolo.com/advanced/websockets/)
- [RFC 6455 - WebSocket Protocol](https://tools.ietf.org/html/rfc6455#section-4)

