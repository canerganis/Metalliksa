/**
 * Decorative boot hero (Phase 9, DESIGN-9 section 4). Lazy chunk; three.js comes from vendor-three.
 * A 64x64 instanced powder bed with a laser spot on a stripe toolpath and a decaying heat tint.
 * It is an illustration only: no solver, no physical units, no data from any model.
 * Mounted only with WebGL, motion allowed and after the runtime-config check. DPR <= 1.5,
 * paused while the tab is hidden, stops animating after 30 consecutive frames slower than 20 ms,
 * and disposes renderer, geometries, materials and observers on unmount.
 */
import React, { useEffect, useRef } from "react";
import {
  AdditiveBlending,
  Color,
  IcosahedronGeometry,
  InstancedMesh,
  Mesh,
  MeshBasicMaterial,
  Object3D,
  PerspectiveCamera,
  Scene,
  WebGLRenderer,
} from "three";

const N = 64;
const GAP = 0.1;
const STRIPE_ROWS = 4;
const STRIPE_SECONDS = 1.6;
const SLOW_FRAME_MS = 20;
const SLOW_FRAME_LIMIT = 30;

function tokenColor(name: string): Color {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return new Color(value || "white");
}

export default function BootHero() {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = host.current;
    if (!container) return undefined;
    // A fresh canvas per mount: a canvas whose context was force-lost cannot host a new renderer.
    const canvas = document.createElement("canvas");
    canvas.setAttribute("aria-hidden", "true");
    container.appendChild(canvas);
    let renderer: WebGLRenderer;
    try {
      renderer = new WebGLRenderer({ canvas, alpha: true, antialias: false, powerPreference: "low-power" });
    } catch {
      canvas.remove();
      return undefined;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));

    const scene = new Scene();
    const camera = new PerspectiveCamera(30, 1, 0.1, 40);
    camera.position.set(0, 2.6, 3.4);
    camera.lookAt(0, 0, 0.3);

    const grainGeometry = new IcosahedronGeometry(0.045, 0);
    const grainMaterial = new MeshBasicMaterial();
    const bed = new InstancedMesh(grainGeometry, grainMaterial, N * N);
    const base = tokenColor("--mk-text-faint");
    const hot = tokenColor("--mk-amber");
    const core = tokenColor("--mk-text-strong");
    const tint = new Float32Array(N * N);
    const heat = new Float32Array(N * N);
    const dummy = new Object3D();
    const color = new Color();
    for (let i = 0; i < N * N; i += 1) {
      const x = i % N;
      const z = Math.floor(i / N);
      dummy.position.set((x - N / 2 + Math.random() * 0.4) * GAP, Math.random() * 0.02, (z - N / 2 + Math.random() * 0.4) * GAP);
      dummy.updateMatrix();
      bed.setMatrixAt(i, dummy.matrix);
      tint[i] = 0.22 + Math.random() * 0.18;
      bed.setColorAt(i, color.copy(base).multiplyScalar(tint[i]));
    }
    scene.add(bed);

    const spotGeometry = new IcosahedronGeometry(0.07, 1);
    const spotMaterial = new MeshBasicMaterial({ color: core, blending: AdditiveBlending, transparent: true });
    const spot = new Mesh(spotGeometry, spotMaterial);
    scene.add(spot);

    const resize = () => {
      const { clientWidth: w, clientHeight: h } = canvas;
      if (!w || !h) return;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    resize();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(resize);
    observer?.observe(canvas);

    let raf = 0;
    let last = 0;
    let slow = 0;
    let time = 0;
    let stopped = false;
    const stripes = N / STRIPE_ROWS;

    const frame = (now: number) => {
      const dt = last ? now - last : 16;
      last = now;
      slow = dt > SLOW_FRAME_MS ? slow + 1 : 0;
      time += Math.min(dt, 50) / 1000;
      const stripe = Math.floor(time / STRIPE_SECONDS) % stripes;
      const s = (time % STRIPE_SECONDS) / STRIPE_SECONDS;
      const gx = (stripe % 2 ? 1 - s : s) * (N - 1);
      const gz = stripe * STRIPE_ROWS + STRIPE_ROWS / 2;
      spot.position.set((gx - N / 2) * GAP, 0.05, (gz - N / 2) * GAP);

      const decay = Math.exp(-dt / 500);
      for (let i = 0; i < heat.length; i += 1) heat[i] *= decay;
      const cx = Math.round(gx);
      for (let dz = -3; dz <= 3; dz += 1) {
        for (let dx = -3; dx <= 3; dx += 1) {
          const x = cx + dx;
          const z = gz + dz;
          if (x < 0 || x >= N || z < 0 || z >= N) continue;
          const i = z * N + x;
          heat[i] = Math.max(heat[i], 1 - Math.hypot(x - gx, z - gz) / 3.2);
        }
      }
      for (let i = 0; i < heat.length; i += 1) {
        const h = heat[i];
        color.copy(base).multiplyScalar(tint[i]);
        if (h > 0.01) color.lerp(hot, Math.min(1, h * 1.4)).lerp(core, Math.max(0, h - 0.75) * 2);
        bed.setColorAt(i, color);
      }
      if (bed.instanceColor) bed.instanceColor.needsUpdate = true;
      renderer.render(scene, camera);
      if (slow >= SLOW_FRAME_LIMIT) {
        stopped = true; // Too slow for this device: keep the last frame, stop animating.
        return;
      }
      raf = requestAnimationFrame(frame);
    };
    const onVisibility = () => {
      cancelAnimationFrame(raf);
      raf = 0;
      last = 0;
      if (!document.hidden && !stopped) raf = requestAnimationFrame(frame);
    };
    document.addEventListener("visibilitychange", onVisibility);
    onVisibility();

    return () => {
      stopped = true;
      cancelAnimationFrame(raf);
      document.removeEventListener("visibilitychange", onVisibility);
      observer?.disconnect();
      bed.dispose();
      grainGeometry.dispose();
      grainMaterial.dispose();
      spotGeometry.dispose();
      spotMaterial.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
      canvas.remove();
    };
  }, []);

  return (
    <figure className="mk-boot-hero">
      <div ref={host} />
      <figcaption>Illustrative — not a simulation result</figcaption>
    </figure>
  );
}
