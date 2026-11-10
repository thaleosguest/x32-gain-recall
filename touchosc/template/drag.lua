-- Glisser de gain d'une voie (généré par touchosc/build_tosc.py) : bouton TRANSPARENT posé sur le potard, qui n'est
-- plus qu'un affichage. Retour de Joseph (27/10, a7) : potard rond en mode relatif « erratique » (tourner autour d'un
-- petit potard = 72 dB en un geste ; garde-fou anti-saut qui annulait les gestes rapides). Ici : glisser VERTICAL,
-- vers le haut = plus, STEP_PX pixels par pas de 0,5 dB, toujours à partir de la valeur affichée (aucun saut possible).
-- Envoi seulement quand le pas change ; le potard bouge tout de suite sous le doigt.

local PATH = '__PATH__'
local KNOB = '__KNOB__'
local DB = '__DB__'
local GMIN, GSPAN = __GMIN__, __GSPAN__
local STEP_PX = __STEP_PX__
local knob, dbl, y0, db0, last

local function round(v)
  return math.floor(v * 2 + 0.5) / 2
end

function init()
  knob = self.parent:findByName(KNOB, false)
  dbl = self.parent:findByName(DB, false)
end

function onPointer(pointers)
  local p = pointers[1]
  if p == nil then return end
  if p.state == PointerState.BEGIN or y0 == nil then
    y0, db0 = p.y, round(GMIN + knob.values.x * GSPAN)
    last = db0
    return
  end
  if p.state == PointerState.END then
    y0 = nil
    return
  end
  local v = round(db0 + (y0 - p.y) / STEP_PX * 0.5)
  v = math.max(GMIN, math.min(GMIN + GSPAN, v))
  if v ~= last then
    last = v
    knob.values.x = (v - GMIN) / GSPAN
    dbl.values.text = string.format('%.1f', v)
    sendOSC(PATH, v + 0.0)
  end
end
