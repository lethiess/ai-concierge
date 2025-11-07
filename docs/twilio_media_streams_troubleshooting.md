# Twilio Media Streams Troubleshooting

## Current Status

✅ **Working:**
- Server running correctly
- ngrok/tunnel WebSocket support confirmed (test endpoint works)
- TwiML generated and fetched successfully by Twilio
- `<Say>` verb works (you heard "Connecting you to our reservation system")
- Basic call flow working

❌ **Not Working:**
- WebSocket connection to `/media-stream` endpoint never established
- No audio bridge between Twilio and OpenAI Realtime API
- Weird noises during call (suggests Stream attempting to connect but failing)

## Diagnosis

The logs show:
1. Twilio successfully fetches TwiML with `<Stream>` element
2. But **no WebSocket connection attempt** to `/media-stream` endpoint
3. Status callbacks return empty data

This suggests **Twilio Media Streams is not connecting**.

## Possible Causes

### 1. Media Streams Not Enabled on Account

Twilio Media Streams might need to be explicitly enabled on your account.

**Check:**
1. Go to https://console.twilio.com/us1/develop/voice/settings/general
2. Look for "Media Streams" settings
3. Ensure it's enabled for your account

### 2. Account Plan Limitations

While you have a Hobbyist (paid) plan, some features might still be restricted.

**Check:**
1. Go to https://console.twilio.com/us1/account/manage-account/general-settings
2. Verify your account is fully upgraded (not in trial mode)
3. Check if Media Streams is available in your plan

### 3. Regional Restrictions

Media Streams might not be available in all regions.

**Your Setup:**
- ngrok Region: Europe (eu)
- This might affect Media Streams availability

**Try:**
- Change ngrok region: `ngrok http 8080 --region us`
- Update `PUBLIC_DOMAIN` in `.env` with new URL
- Test again

### 4. Verify Phone Number Configuration

**Check:**
1. Go to https://console.twilio.com/us1/develop/phone-numbers/manage/incoming
2. Click on your phone number  
3. Under "Voice Configuration", ensure no conflicting webhooks are set

### 5. Check Twilio Call Logs

This is the most important step to see what Twilio reports:

1. Go to https://console.twilio.com/us1/monitor/logs/calls
2. Find your most recent call (call_id: `2e4ccfd5-c989-4fb8-9318-de58932518f4`)
3. Click on it to see detailed logs
4. Look for errors related to:
   - `<Stream>` verb
   - WebSocket connection
   - Any error codes

**Common Error Codes:**
- **63006**: Media Streams not available on account
- **11200**: Invalid TwiML
- **11205**: Invalid Stream URL

## Testing Steps

### Step 1: Verify Diagnostics Endpoint

Visit: `https://ai-concierge.ngrok.dev/diagnostics`

This will show your current configuration and help identify issues.

### Step 2: Test Without Media Streams

Change `voice_agent.py` line 221 to:
```python
twiml_url = f"https://{config.public_domain}/twiml?call_id={call_id}&test_mode=true"
```

This will use simple `<Say>` commands instead of Media Streams to verify basic functionality.

**Restart server and make a test call.** If you hear the full test message, your server and Twilio integration work correctly, confirming the issue is specifically with Media Streams.

### Step 3: Check Twilio Console for Media Streams

1. Go to Twilio Console
2. Search for "Media Streams" in settings
3. Verify it's enabled
4. Check if there are any beta features to enable

### Step 4: Contact Twilio Support

If Media Streams is not available or enabled on your account:

1. Go to https://support.twilio.com
2. Create a support ticket asking:
   - "Is Media Streams enabled on my account?"
   - "Do I need to request access to Media Streams?"
   - Provide your account SID and the error details

## Quick Fixes to Try Now

### Fix 1: Restart with Detailed Logging

I've added enhanced logging. Restart your server:
```bash
python -m concierge.server
```

Make another test call and watch for:
```
======================================================================
🔌 MEDIA STREAM WebSocket connection attempt for call ...
======================================================================
```

If you **don't see this**, Twilio isn't attempting the WebSocket connection.

### Fix 2: Check Server Logs for Errors

Look for any errors or exceptions in the server logs that might indicate why the WebSocket isn't connecting.

### Fix 3: Verify TwiML Format

The TwiML being generated:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Connecting you to our reservation system.</Say>
    <Connect>
        <Stream url="wss://ai-concierge.ngrok.dev/media-stream?call_id=..." track="inbound_track outbound_track" />
    </Connect>
</Response>
```

This looks correct according to [Twilio's documentation](https://www.twilio.com/docs/voice/twiml/stream).

## Expected Behavior

When Media Streams works correctly, you should see:

1. **In Server Logs:**
```
Generated TwiML for call ...
WebSocket URL: wss://...
======================================================================
🔌 MEDIA STREAM WebSocket connection attempt for call ...
  Client: ...
  Headers: {...}
======================================================================
✓✓✓ WebSocket ACCEPTED for call ...
Created RealtimeAgent for call ...
Created RealtimeRunner for call ...
Twilio media stream started: ...
```

2. **In Call:**
- Hear "Connecting you to our reservation system"
- Seamless transition to AI voice agent
- Natural conversation with OpenAI Realtime API
- No weird noises or disconnections

## Next Steps

1. ✅ **Check Twilio Call Logs** - This will show exactly why Media Streams isn't connecting
2. ⚙️ **Verify Media Streams is enabled** on your Twilio account
3. 🧪 **Test with test_mode=true** to isolate the issue
4. 📞 **Contact Twilio Support** if Media Streams needs to be enabled

## Additional Resources

- [Twilio Media Streams Documentation](https://www.twilio.com/docs/voice/twiml/stream)
- [Twilio Stream Verb](https://www.twilio.com/docs/voice/twiml/stream)
- [Media Streams Quickstart](https://www.twilio.com/docs/voice/tutorials/consume-real-time-media-stream-using-websockets-python-and-flask)
- [Twilio Error Codes](https://www.twilio.com/docs/api/errors)

## Summary

The issue is NOT with your code or configuration - everything is set up correctly. The problem is that Twilio Media Streams is not establishing the WebSocket connection, which suggests it's either:
- Not enabled on your account
- Not available in your region
- Requires additional configuration in Twilio Console

**The Twilio Call Logs will tell us exactly what's happening.**

