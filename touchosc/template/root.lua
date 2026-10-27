-- X/M32 Gain Recall for eMotion LV1 : script racine du template TouchOSC (généré par touchosc/build_tosc.py).
-- Chaque TouchOSC fait tourner ce script et parle LUI-MÊME à Gain Recall, y compris une tablette cliente du réseau de
-- l'éditeur (qui ne reçoit que le document) : sur la tablette, Host = adresse du PC de la LV1.
-- /xgr/hello toutes les secondes ; Gain Recall répond /xgr/welcome puis envoie l'état quand il change (protocol.py).
-- Les valeurs PROTO / ports sont remplacées à la génération (touchosc/protocol.py est la référence).

local PROTO = __PROTO__
local HELLO_MS = 1000
local LOST_MS = 3500
local NOTIFY_MS = 6000

local BLUE = Color(56 / 255, 201 / 255, 1, 1)        -- bleu « actif » de la LV1
local TEXT = Color(231 / 255, 231 / 255, 231 / 255, 1)
local GREY = Color(0.35, 0.35, 0.35, 1)
local MUTED = Color(160 / 255, 160 / 255, 160 / 255, 1)
local ORANGE = Color(1, 0.6, 0.15, 1)

local lastHello = -HELLO_MS
local lastSeen = nil
local shown = nil
local notifyAt = nil
local c = {}                                          -- contrôles par nom

-- état reçu (adresse -> nom du LABEL qui affiche le texte)
local TEXTS = { ['/xgr/console'] = 'console', ['/xgr/lv1'] = 'lv1' }

function init()
  for _, name in ipairs({ 'led', 'status', 'detail', 'console', 'lv1', 'tablets', 'notify', 'sync' }) do
    c[name] = self:findByName(name, true)
  end
  -- alignement et forme par les constantes Lua (valeurs numériques du fichier non documentées)
  for _, name in ipairs({ 'title', 'footer', 'console', 'lv1', 'tablets', 'k_console', 'k_lv1', 'k_tablets' }) do
    self:findByName(name, true).textAlignH = AlignH.LEFT
  end
  c.led.shape = Shape.CIRCLE
  c.sync.outlineStyle = OutlineStyle.FULL
end

local function show(alive, text, sub, color)
  c.led.color = color
  c.status.values.text = text
  c.detail.values.text = sub
  shown = alive
  if not alive then
    c.console.values.text = '-'
    c.lv1.values.text = '-'
    c.tablets.values.text = '-'
  end
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
         'Connections > OSC (UDP): Host = LV1 PC address (127.0.0.1 on that PC), Send Port __PORT_IN__, Receive Port __PORT_OUT__',
         GREY)
  end
  if notifyAt ~= nil and now - notifyAt > NOTIFY_MS then
    c.notify.values.text = ''
    notifyAt = nil
  end
end

function onReceiveOSC(message, connections)
  local path, args = message[1], message[2]
  if path == '/xgr/welcome' then
    lastSeen = getMillis()
    local version, console, state = args[2].value, args[3].value, args[4].value
    if state == 'ok' then
      show(true, 'Connected to X/M32 Gain Recall ' .. version, 'Console: ' .. console, BLUE)
    elseif state == 'pending' then
      show(true, 'Waiting for approval', 'Allow this tablet in X/M32 Gain Recall, on the LV1 PC', ORANGE)
    elseif state == 'old_template' then
      show(true, 'Template out of date', 'Get the template that comes with Gain Recall ' .. version, ORANGE)
    else
      show(true, 'Gain Recall out of date', 'This template needs a newer Gain Recall (running ' .. version .. ')', ORANGE)
    end
    return true
  end
  local name = TEXTS[path]
  if name then
    c[name].values.text = args[1].value
    return true
  end
  if path == '/xgr/console/ok' then
    c.console.textColor = (args[1].value == 1) and TEXT or MUTED
    return true
  end
  if path == '/xgr/tablets' then
    -- instances TouchOSC qui parlent à Gain Recall (mode serveur : 1, le PC ; les tablettes clientes n'y comptent pas)
    c.tablets.values.text = math.floor(args[1].value) .. ' connected'
    return true
  end
  if path == '/xgr/notify' then
    c.notify.values.text = args[1].value
    notifyAt = getMillis()
    return true
  end
  return false
end
