-- Glisser du fader LV1 d'une tranche (généré par touchosc/build_tosc.py, phase 5b) : bouton TRANSPARENT posé sur la
-- colonne du fader. Glisser VERTICAL relatif, 1:1 avec la course dessinée, toujours à partir de la position affichée
-- (aucun saut) ; dB d'après la courbe de la LV1 (views.LV1_FADER), au dixième. Envois espacés de SEND_MS au plus, la
-- valeur finale part toujours au lâcher.

local PATH = '__PATH__'
local FADER, FVAL = '__FADER__', '__FVAL__'
local H = __H__
local CURVE = __CURVE__
local SEND_MS = 30
local fader, fval, y0, pos0, last, pending, sentAt

local function dbOf(pos)
  if pos <= 0 then return -144.0 end
  if pos >= 1 then return CURVE[1][1] end
  for i = 1, #CURVE - 1 do
    local d1, p1, d2, p2 = CURVE[i][1], CURVE[i][2], CURVE[i + 1][1], CURVE[i + 1][2]
    if pos <= p1 and pos >= p2 then
      return math.floor((d2 + (d1 - d2) * (pos - p2) / (p1 - p2)) * 10 + 0.5) / 10
    end
  end
  return -144.0
end

function init()
  fader = self.parent:findByName(FADER, false)
  fval = self.parent:findByName(FVAL, false)
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
    y0, pos0, last = p.y, fader.values.x, nil
    return
  end
  if p.state == PointerState.END then
    y0 = nil
    flush(true)
    return
  end
  local pos = math.max(0, math.min(1, pos0 + (y0 - p.y) / H))
  local db = dbOf(pos)
  fader.values.x = pos
  if db ~= last then
    last = db
    fval.values.text = string.format('%.1f', db)
    pending = db
  end
  flush(false)
end

function update()
  flush(false)
end
