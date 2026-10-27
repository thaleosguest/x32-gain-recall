-- Bouton 48V d'une voie (généré par touchosc/build_tosc.py, phase 2b) : bouton transparent posé sur la case 48V.
-- 1er appui : « OK? » pendant 3 s ; 2e appui dans ce délai : bascule demandée à Gain Recall (qui part de l'état connu
-- de la console et refuse tant qu'il ne l'a pas lu). Le script racine colore la case selon l'état reçu.

local PATH = '__PATH__'
local LABEL = '__LABEL__'
local ARM_MS = 3000
local armedAt = nil
local lbl

function init()
  lbl = self.parent:findByName(LABEL, false)
end

function onValueChanged(key)
  if key ~= 'x' or self.values.x ~= 1 then return end
  local now = getMillis()
  if armedAt ~= nil and now - armedAt < ARM_MS then
    armedAt = nil
    lbl.values.text = '48V'
    sendOSC(PATH)
  else
    armedAt = now
    lbl.values.text = 'OK?'
  end
end

function update()
  if armedAt ~= nil and getMillis() - armedAt >= ARM_MS then
    armedAt = nil
    lbl.values.text = '48V'
  end
end
