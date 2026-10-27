-- Glisser du pan LV1 d'une tranche (généré par touchosc/build_tosc.py, phase 5b) : bouton TRANSPARENT sur le potard.
-- Glisser HORIZONTAL relatif (à droite = vers la droite), PX_FULL pixels pour aller du centre à un côté, par pas de 1/45
-- (comme la X-Touch) ; envois espacés de SEND_MS au plus, la valeur finale part au lâcher.

local PATH = '__PATH__'
local KNOB = '__KNOB__'
local PX_FULL = __PX_FULL__
local SEND_MS = 30
local knob, x0, pan0, last, pending, sentAt

function init()
  knob = self.parent:findByName(KNOB, false)
end

local function flush(force)
  local now = getMillis()
  if pending ~= nil and (force or sentAt == nil or now - sentAt >= SEND_MS) then
    sendOSC(PATH, pending + 0.0)
    pending, sentAt = nil, now
  end
end

function onPointer(pointers)
  local p = pointers[1]
  if p == nil then return end
  if p.state == PointerState.BEGIN or x0 == nil then
    x0, pan0, last = p.x, knob.values.x * 2 - 1, nil
    return
  end
  if p.state == PointerState.END then
    x0 = nil
    flush(true)
    return
  end
  local pan = math.max(-1, math.min(1, pan0 + (p.x - x0) / PX_FULL))
  pan = math.floor(pan * 45 + 0.5) / 45
  if pan ~= last then
    last = pan
    knob.values.x = (pan + 1) / 2
    pending = pan
  end
  flush(false)
end

function update()
  flush(false)
end
