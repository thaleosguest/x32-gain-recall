-- Onglet de page (généré par touchosc/build_tosc.py, phase 3a) : n'affiche que la page PAGE, sur CETTE tablette
-- (rien n'est envoyé) ; FOLLOW / titre de couche seulement sur MIXER (la rangée des couches est dans la page Mixer).

local PAGE = '__PAGE__'
local PAGES = { 'mixer', 'scenes', 'routing' }
local BLUE = Color(56 / 255, 201 / 255, 1, 1)
local TEXT = Color(231 / 255, 231 / 255, 231 / 255, 1)

function onValueChanged(key)
  if key ~= 'x' or self.values.x ~= 1 then return end
  local root = self.parent
  for _, p in ipairs(PAGES) do
    root:findByName('page_' .. p, false).visible = (p == PAGE)
    root:findByName('tab_' .. p .. '_label', false).textColor = (p == PAGE) and BLUE or TEXT
  end
  local mixer = (PAGE == 'mixer')
  for _, name in ipairs({ 'follow', 'follow_label', 'g_title' }) do
    root:findByName(name, false).visible = mixer
  end
end
