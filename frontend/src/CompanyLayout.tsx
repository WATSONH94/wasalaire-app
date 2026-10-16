import { Outlet } from 'react-router-dom'

// Le contexte société est porté par le fil d'Ariane (topbar) et la navigation latérale
// (markup Stitch) ; chaque écran affiche son propre en-tête. Pas d'onglets redondants.
export default function CompanyLayout() {
  return <Outlet />
}
