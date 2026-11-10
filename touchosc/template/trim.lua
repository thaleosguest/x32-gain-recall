-- Glisser du Trim LV1 d'une tranche (généré par touchosc/build_tosc.py, phase 5b) : bouton TRANSPARENT sur la zone
-- Trim. Glisser VERTICAL relatif, STEP_PX pixels par pas de 0,5 dB, à partir de la valeur affichée, borné à ±LIMIT (la
-- LV1 borne elle-même et renvoie la vraie valeur) ; potard sur ±SPAN dB. Envois espacés de SEND_MS au plus.

local PATH = '__PATH__'
local KNOB, VAL = '__KNOB__', '__VAL__'
local STEP_PX, LIMIT, SPAN = __STEP_PX__, __LIMIT__, __SPAN__
local SEND_MS = 30
local knob, val, y0, t0, last, pending, sentAt

function init()
  knob = self.parent:findByName(KNOB, false)
  val = self.parent:findByName(VAL, false)
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
  if p.state == PointerState.BEGIN or y0 == nil then
    y0, t0, last = p.y, tonumber(val.values.text) or 0.0, nil
    return
  end
  if p.state == PointerState.END then
    y0 = nil
    flush(true)
    return
  end
  local v = t0 + math.floor((y0 - p.y) / STEP_PX + 0.5) * 0.5
  v = math.max(-LIMIT, math.min(LIMIT, v))
  if v ~= last then
    last = v
    val.values.text = string.format('%.1f', v)
    knob.values.x = math.max(0, math.min(1, (v + SPAN) / (2 * SPAN)))
    pending = v
  end
  flush(false)
end

function update()
  flush(false)
end
