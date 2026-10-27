-- X/M32 Gain Recall for eMotion LV1 : script racine du template TouchOSC (généré par touchosc/build_tosc.py).
-- Chaque TouchOSC fait tourner ce script et parle LUI-MÊME à Gain Recall, y compris une tablette cliente du réseau de
-- l'éditeur (qui ne reçoit que le document) : sur la tablette, Host = adresse du PC de la LV1.
-- /xgr/hello toutes les secondes ; Gain Recall répond /xgr/welcome puis envoie l'état quand il change (protocol.py).
-- Les valeurs PROTO / ports sont remplacées à la génération (touchosc/protocol.py est la référence).

local PROTO = __PROTO__
local STRIPS = __STRIPS__
local HELLO_MS = 1000
local LOST_MS = 3500
local NOTIFY_MS = 6000

local BLUE = Color(56 / 255, 201 / 255, 1, 1)        -- bleu « actif » de la LV1
local TEXT = Color(231 / 255, 231 / 255, 231 / 255, 1)
local GREY = Color(0.35, 0.35, 0.35, 1)
local MUTED = Color(160 / 255, 160 / 255, 160 / 255, 1)
local DARK = Color(43 / 255, 43 / 255, 43 / 255, 1)
local ORANGE = Color(1, 0.6, 0.15, 1)
local RED = Color(209 / 255, 52 / 255, 59 / 255, 1)  -- 48V actif, comme le float (PH_ON)

local lastHello = -HELLO_MS
local lastSeen = nil
local shown = nil
local notifyAt = nil
local c = {}                                          -- contrôles par nom
local UNITS = { 'm', 'l', 'r' }
local BANKS = 5
local srv = {}                                        -- potard -> dernière valeur de la console (0..1)
local srvDb = {}                                      -- potard -> dernier texte dB de la console
local lastResync = 0
local HOLD_MS = 1000                                  -- après un glisser : retours de la console ignorés (comme le float)
local holdUntil, wasDragging = {}, {}

local function dragging(name)
  -- name = potard « gK_U_knob » ; le geste passe par le bouton transparent « gK_U_drag » posé dessus
  local d = c[name:gsub('_knob$', '_drag')]
  return d ~= nil and d.values.touch
end

local function busy(name, now)
  -- sous le doigt, ou lâché il y a moins de HOLD_MS : la valeur affichée est celle du geste
  local on = dragging(name)
  if on then
    wasDragging[name] = true
  elseif wasDragging[name] then
    wasDragging[name] = nil
    holdUntil[name] = now + HOLD_MS
  end
  return on or (holdUntil[name] ~= nil and now < holdUntil[name])
end
local curBank, nBanks = -1, BANKS                     -- banque affichée (-1 : couche sans banque), banques proposées

-- Commandes de la LV1 (phase 5a, lecture seule) : « gK_ » pour une tranche, « lr_ » pour LR. Couleurs d'état comme la
-- LV1 : MUTE actif rouge, CUE / Ø / entrée sélectionnée bleus ; tout gris tant que la LV1 n'est pas connectée.
local OFF = Color(90 / 255, 90 / 255, 90 / 255, 1)
local PANEL = Color(17 / 255, 17 / 255, 17 / 255, 1)
local INK = PANEL
local MIX_PARTS = { 'fader', 'fval', 'peak', 'meter', 'mute', 'mute_l', 'cue', 'cue_l', 'pan', 'pan_a', 'trim',
                    'trim_v', 'trim_t', 'phase', 'phase_l', 'a', 'a_l', 'b', 'b_l' }
local live = false
local mixState = {}                                   -- « gK_mute » … -> dernière valeur reçue (repeinte par setLive)

local function paintKey(p, part, on, onColor)
  -- case de la LV1 (box + libellé « _l ») : allumée = fond de la couleur d'état, texte INK ; éteinte = fond sombre
  local b, l = c[p .. part], c[p .. part .. '_l']
  if b == nil then return end
  b.color = (live and on) and onColor or PANEL
  l.textColor = (not live) and OFF or (on and INK or TEXT)
end

function setMix(p, field, v)
  mixState[p .. field] = v
  if field == 'fader' or field == 'meter' or field == 'pan' or field == 'trim' then
    local ctl = c[p .. field]
    if ctl then ctl.values.x = v end
  elseif field == 'fval' or field == 'peak' then
    c[p .. field].values.text = v
  elseif field == 'trimv' then
    c[p .. 'trim_v'].values.text = v
  elseif field == 'mute' then
    paintKey(p, 'mute', v == 1, RED)
  elseif field == 'solo' then
    paintKey(p, 'cue', v == 1, BLUE)
  elseif field == 'phase' then
    paintKey(p, 'phase', v == 1, BLUE)
  elseif field == 'ab' then
    paintKey(p, 'a', v == 'A', BLUE)
    paintKey(p, 'b', v == 'B', BLUE)
  end
end

local function setLive(on)
  live = on
  local prefixes = { 'lr_' }
  for k = 1, STRIPS do prefixes[#prefixes + 1] = 'g' .. k .. '_' end
  for _, p in ipairs(prefixes) do
    for _, part in ipairs({ 'fval', 'trim_v' }) do
      if c[p .. part] then c[p .. part].textColor = on and BLUE or OFF end
    end
    for _, part in ipairs({ 'peak', 'trim_t', 'pan_a' }) do
      if c[p .. part] then c[p .. part].textColor = on and TEXT or OFF end
    end
    for _, part in ipairs({ 'fader', 'pan', 'trim' }) do
      if c[p .. part] then c[p .. part].color = on and MUTED or OFF end
    end
    for _, f in ipairs({ 'mute', 'solo', 'phase', 'ab' }) do
      if mixState[p .. f] ~= nil then setMix(p, f, mixState[p .. f]) end
    end
  end
end

function paintBanks()
  -- (bank et banks arrivent dans n'importe quel ordre : on repeint les deux à chaque fois)
  for i = 0, BANKS - 1 do
    c['bank' .. i].interactive = i < nBanks
    c['bank' .. i .. '_label'].textColor = (i >= nBanks) and GREY or ((i == curBank) and BLUE or TEXT)
  end
end

-- textes de la barre d'état (adresse -> LABEL, préfixe)
local TEXTS = { ['/xgr/console'] = { 'console', 'Console: ' }, ['/xgr/lv1'] = { 'lv1', '' } }

local function hexColor(h)
  if h == nil or #h ~= 6 then return nil end
  return Color(tonumber(h:sub(1, 2), 16) / 255, tonumber(h:sub(3, 4), 16) / 255, tonumber(h:sub(5, 6), 16) / 255, 1)
end

function init()
  for _, name in ipairs({ 'led', 'status', 'detail', 'console', 'lv1', 'tablets', 'notify', 'sync', 'panel',
                          'panel_line', 'g_title', 'follow_label' }) do
    c[name] = self:findByName(name, true)
  end
  for n = 0, BANKS - 1 do
    c['bank' .. n] = self:findByName('bank' .. n, true)
    c['bank' .. n .. '_label'] = self:findByName('bank' .. n .. '_label', true)
  end
  for k = 1, STRIPS do
    for _, part in ipairs({ 'srcbox', 'input', 'band', 'name', 'src', 'numbar', 'num' }) do
      local n = 'g' .. k .. '_' .. part
      c[n] = self:findByName(n, true)
    end
    for _, part in ipairs(MIX_PARTS) do
      local n = 'g' .. k .. '_' .. part
      c[n] = self:findByName(n, true)
    end
    for _, u in ipairs(UNITS) do
      for _, part in ipairs({ 'knob', 'drag', 'db', '48', '48l', '48b' }) do
        local n = 'g' .. k .. '_' .. u .. '_' .. part
        c[n] = self:findByName(n, true)
      end
    end
  end
  -- alignement et forme par les constantes Lua (valeurs numériques du fichier non documentées)
  for _, name in ipairs({ 'title', 'footer', 'console', 'lv1' }) do
    self:findByName(name, true).textAlignH = AlignH.LEFT
  end
  for k = 1, STRIPS do                                  -- numéro de canal à droite de son bandeau, comme la LV1
    c['g' .. k .. '_num'].textAlignH = AlignH.RIGHT
  end
  self:findByName('lr_num', true).textAlignH = AlignH.RIGHT
  for _, part in ipairs(MIX_PARTS) do
    c['lr_' .. part] = self:findByName('lr_' .. part, true)       -- nil pour ce que LR n'a pas (pan, Trim, A / B…)
  end
  c.led.shape = Shape.CIRCLE
  c.sync.outlineStyle = OutlineStyle.FULL
  self:findByName('follow', true).outlineStyle = OutlineStyle.FULL   -- (par défaut : coins, vus comme des crochets)
  for n = 0, BANKS - 1 do
    c['bank' .. n].outlineStyle = OutlineStyle.FULL
  end
  for k = 1, STRIPS do
    setUnits(k, 0)
  end
end

function setUnits(k, n)
  -- 0 voie : rien ; 1 : « m » au centre ; 2 : « l » et « r » côte à côte (canal stéréo, gains non liés, comme le float)
  local show = { m = (n == 1), l = (n == 2), r = (n == 2) }
  for _, u in ipairs(UNITS) do
    for _, part in ipairs({ 'knob', 'drag', 'db', '48', '48l', '48b' }) do
      c['g' .. k .. '_' .. u .. '_' .. part].visible = show[u]
    end
  end
end

local function show(alive, ok, text, sub, color)
  c.led.color = color
  c.status.values.text = text
  c.detail.values.text = sub
  for _, name in ipairs({ 'panel', 'panel_line', 'status', 'detail' }) do
    c[name].visible = not ok
  end
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
    show(false, false, 'Looking for X/M32 Gain Recall...',
         'Connections > OSC (UDP): Host = LV1 PC address (127.0.0.1 on that PC), Send Port __PORT_IN__, Receive Port __PORT_OUT__',
         GREY)
  end
  if now - lastResync > 200 then
    -- potard lâché depuis plus de HOLD_MS : calé sur la valeur de la console
    lastResync = now
    for name, v in pairs(srv) do
      local knob = c[name]
      if not busy(name, now) then
        if math.abs(knob.values.x - v) > 0.0005 then knob.values.x = v end
        local dbl = c[name:gsub('_knob$', '_db')]
        if srvDb[name] and dbl.values.text ~= srvDb[name] then dbl.values.text = srvDb[name] end
      end
    end
  end
  if notifyAt ~= nil and now - notifyAt > NOTIFY_MS then
    c.notify.values.text = ''
    notifyAt = nil
  end
end

local function onStrip(k, field, v)
  local g = 'g' .. k .. '_'
  if field == 'name' then
    c[g .. 'name'].values.text = v
  elseif field == 'input' then
    c[g .. 'input'].values.text = v
  elseif field == 'ch' then
    local n = math.floor(v)
    c[g .. 'num'].values.text = (n > 0) and tostring(n) or ''
  elseif field == 'src' then
    c[g .. 'src'].values.text = v
  elseif field == 'color' then
    -- comme la LV1 : bouton de source, bandeau du nom et bandeau du numéro à la couleur du canal
    local col = hexColor(v)
    for _, part in ipairs({ 'srcbox', 'band', 'numbar' }) do
      c[g .. part].color = col or DARK
    end
    for _, u in ipairs(UNITS) do
      c[g .. u .. '_knob'].color = col or MUTED
    end
  elseif field == 'units' then
    setUnits(k, math.floor(v))
  else
    setMix(g, field, v)                       -- commandes de la LV1 (fader, mute, solo, pan, trim, phase, ab…)
  end
end

local function onUnit(k, u, field, v)
  local g = 'g' .. k .. '_' .. u .. '_'
  if field == 'gain' then
    srv[g .. 'knob'] = v
    if not busy(g .. 'knob', getMillis()) then   -- glisser en cours ou tout juste fini : le retour ne s'y oppose pas
      c[g .. 'knob'].values.x = v
    end
  elseif field == 'db' then
    srvDb[g .. 'knob'] = v
    if not busy(g .. 'knob', getMillis()) then c[g .. 'db'].values.text = v end
  elseif field == '48v' then
    local on = math.floor(v) == 1
    c[g .. '48'].color = on and RED or DARK
    c[g .. '48l'].textColor = on and TEXT or MUTED
  end
end

function onReceiveOSC(message, connections)
  local path, args = message[1], message[2]
  if path == '/xgr/welcome' then
    lastSeen = getMillis()
    local version, console, state = args[2].value, args[3].value, args[4].value
    if state == 'ok' then
      show(true, true, 'Connected to X/M32 Gain Recall ' .. version, 'Console: ' .. console, BLUE)
    elseif state == 'pending' then
      show(true, false, 'Waiting for approval', 'Allow this tablet in X/M32 Gain Recall, on the LV1 PC', ORANGE)
    elseif state == 'old_template' then
      show(true, false, 'Template out of date', 'Get the template that comes with Gain Recall ' .. version, ORANGE)
    else
      show(true, false, 'Gain Recall out of date', 'This template needs a newer Gain Recall (running ' .. version .. ')', ORANGE)
    end
    return true
  end
  local k, u, field = path:match('^/xgr/g/(%d+)/([mlr])/(%w+)$')
  if k then
    onUnit(tonumber(k), u, field, args[1].value)
    return true
  end
  k, field = path:match('^/xgr/g/(%d+)/(%a+)$')
  if k then
    onStrip(tonumber(k), field, args[1].value)
    return true
  end
  local lf = path:match('^/xgr/lr/(%a+)$')
  if lf then
    setMix('lr_', lf, args[1].value)
    return true
  end
  if path == '/xgr/live' then
    setLive(math.floor(args[1].value) == 1)
    return true
  end
  if path == '/xgr/view/follow' then
    c.follow_label.textColor = (args[1].value == 1) and BLUE or TEXT
    return true
  end
  if path == '/xgr/view/bank' then
    curBank = math.floor(args[1].value)
    paintBanks()
    return true
  end
  if path == '/xgr/view/banks' then
    -- banques au-delà de la configuration de la LV1 (64 canaux : pas de 65-80) : grisées, sans effet
    nBanks = math.floor(args[1].value)
    paintBanks()
    return true
  end
  if path == '/xgr/g/title' then
    c.g_title.values.text = args[1].value
    return true
  end
  local t = TEXTS[path]
  if t then
    c[t[1]].values.text = t[2] .. args[1].value
    return true
  end
  if path == '/xgr/console/ok' then
    c.console.textColor = (args[1].value == 1) and TEXT or MUTED
    return true
  end
  if path == '/xgr/tablets' then
    -- instances TouchOSC qui parlent à Gain Recall
    c.tablets.values.text = 'TouchOSC: ' .. math.floor(args[1].value)
    return true
  end
  if path == '/xgr/notify' then
    c.notify.values.text = args[1].value
    notifyAt = getMillis()
    return true
  end
  return false
end
