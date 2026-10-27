-- Potard de gain d'une voie (généré par touchosc/build_tosc.py, phase 2b).
-- RELATIF (on glisse, il ne saute pas à l'endroit touché) ; n'envoie que pendant un toucher, le dB voulu arrondi à
-- 0,5 dB, seulement quand il change. Garde-fou : un saut de plus de 3 dB d'un coup (potard resté en absolu) bloque le
-- geste jusqu'au prochain toucher ; le script racine remet ensuite le potard sur la valeur de la console.

local PATH = '__PATH__'
local GMIN, GSPAN = __GMIN__, __GSPAN__
local last = nil

local function db(x)
  return math.floor((GMIN + x * GSPAN) * 2 + 0.5) / 2
end

function init()
  if Response then self.response = Response.RELATIVE end
end

function onValueChanged(key)
  if key == 'touch' then
    last = self.values.touch and db(self.values.x) or nil
    return
  end
  if key ~= 'x' or not self.values.touch or last == nil then return end
  local v = db(self.values.x)
  if v == last then return end
  if math.abs(v - last) > 3 then
    last = nil
    return
  end
  last = v
  sendOSC(PATH, v)
end
