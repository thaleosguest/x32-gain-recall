-- X/M32 Gain Recall for eMotion LV1 : script racine du template TouchOSC (généré par touchosc/build_tosc.py).
-- Phase 0 : présence. /xgr/hello toutes les secondes, /xgr/welcome en retour -> voyant + état affiché.
-- Les valeurs PROTO / ports sont remplacées à la génération (touchosc/protocol.py est la référence).

local PROTO = __PROTO__
local HELLO_MS = 1000
local LOST_MS = 3500

local BLUE = Color(56 / 255, 201 / 255, 1, 1)        -- bleu « actif » de la LV1
local GREY = Color(0.35, 0.35, 0.35, 1)
local ORANGE = Color(1, 0.6, 0.15, 1)

local lastHello = -HELLO_MS
local lastSeen = nil
local shown = nil
local led, status, detail

function init()
  led = self:findByName('led', true)
  status = self:findByName('status', true)
  detail = self:findByName('detail', true)
end

local function show(alive, text, sub, color)
  led.color = color
  status.values.text = text
  detail.values.text = sub
  shown = alive
end

function update()
  local now = getMillis()
  if now - lastHello >= HELLO_MS then
    lastHello = now
    sendOSC('/xgr/hello', PROTO, 'TouchOSC')
  end
  local alive = lastSeen ~= nil and now - lastSeen < LOST_MS
  if not alive and shown ~= false then
    show(false, 'Looking for X/M32 Gain Recall...',
         'TouchOSC > Connections > OSC (UDP): Host = LV1 PC address, Send Port __PORT_IN__, Receive Port __PORT_OUT__',
         GREY)
  end
end

function onReceiveOSC(message, connections)
  local path, args = message[1], message[2]
  if path ~= '/xgr/welcome' then
    return false
  end
  lastSeen = getMillis()
  local version, console, state = args[2].value, args[3].value, args[4].value
  if state == 'ok' then
    show(true, 'Connected to X/M32 Gain Recall ' .. version, 'Console: ' .. console, BLUE)
  elseif state == 'old_template' then
    show(true, 'Template out of date', 'Get the template that comes with Gain Recall ' .. version, ORANGE)
  else
    show(true, 'Gain Recall out of date', 'This template needs a newer Gain Recall (running ' .. version .. ')', ORANGE)
  end
  return true
end
