-- Bouton RECALL de la page SCENES (généré par touchosc/build_tosc.py, phase 3a) : bouton transparent sur la case.
-- 1er appui : « OK? » pendant ARM_MS ; 2e appui dans ce délai : rappel de la scène sélectionnée (id dans le libellé
-- caché « sc_selid »), avec le 48V si « + 48V » est allumé (libellé caché « sc_ph »). Sans sélection : consigne.

local ARM_MS = 3000
local armedAt, msgAt = nil, nil
local lbl, selid, ph

function init()
  lbl = self.parent:findByName('sc_recall_l', false)
  selid = self.parent:findByName('sc_selid', false)
  ph = self.parent:findByName('sc_ph', false)
end

local function reset()
  armedAt, msgAt = nil, nil
  lbl.values.text = 'RECALL'
end

function onValueChanged(key)
  if key ~= 'x' or self.values.x ~= 1 then return end
  local now = getMillis()
  if selid.values.text == '' then
    lbl.values.text = 'SELECT A SCENE'
    armedAt, msgAt = nil, now
    return
  end
  if armedAt ~= nil and now - armedAt < ARM_MS then
    sendOSC('/xgr/sc/recall', selid.values.text, (ph.values.text == '1') and 1 or 0)
    reset()
  else
    armedAt = now
    lbl.values.text = 'OK?'
  end
end

function update()
  local now = getMillis()
  if (armedAt ~= nil and now - armedAt >= ARM_MS) or (msgAt ~= nil and now - msgAt >= ARM_MS) then
    reset()
  end
end
