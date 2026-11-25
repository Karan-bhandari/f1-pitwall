import { createRouter, createWebHistory } from "vue-router";
import SeasonHubView from "../views/SeasonHubView.vue";
import RacePitWallView from "../views/RacePitWallView.vue";
import DriversView from "../views/DriversView.vue";
import ConstructorsView from "../views/ConstructorsView.vue";
import LivePitWallView from "../views/LivePitWallView.vue";

const routes = [
  {
    path: "/",
    name: "season-hub",
    component: SeasonHubView,
  },
  {
    path: "/race/:event?",
    name: "race-pitwall",
    component: RacePitWallView,
  },
  {
    path: "/live",
    name: "live-pitwall",
    component: LivePitWallView,
  },
  {
    path: "/drivers",
    name: "drivers",
    component: DriversView,
  },
  {
    path: "/constructors",
    name: "constructors",
    component: ConstructorsView,
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior() {
    return { top: 0 };
  },
});

export default router;
