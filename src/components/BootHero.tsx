/**
 * Decorative boot hero: a WebGL spark layer laid over the foundry artwork (FoundryStage). Sparks are
 * thrown from the melt point where the beam meets the sphere, drawn as short additive streaks with hot
 * heads, pulled down by gravity and cooling from white through amber to nothing. Lazy chunk; three.js
 * comes from vendor-three. It is an illustration only: no solver, no physical units, no data from any model.
 * Mounted only with WebGL, motion allowed and after the runtime-config check. DPR <= 1.5, paused while the
 * tab is hidden, after 30 consecutive frames slower than 20 ms it clears the sparks and stops (the
 * artwork stays), and disposes renderer, geometries, materials and observers on unmount.
 */
import React, { useEffect, useRef } from "react";
import {
  AdditiveBlending,
  BufferAttribute,
  BufferGeometry,
  CanvasTexture,
  LineBasicMaterial,
  LineSegments,
  OrthographicCamera,
  Points,
  PointsMaterial,
  Scene,
  WebGLRenderer,
} from "three";

const COUNT = 260;
const SLOW_FRAME_MS = 20;
const SLOW_FRAME_LIMIT = 30;
// Melt pool in the artwork, as a fraction of the frame (matches --hx / --hy in foundry.css).
const HIT_X = 0.677;
const HIT_Y = 0.547;

/** Soft round sprite for the spark heads (drawn once on a small canvas, no image file). */
function glowTexture(): CanvasTexture {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const g = canvas.getContext("2d");
  if (g) {
    // White sprite with a radial alpha falloff, written pixel by pixel (no colour literals).
    const img = g.createImageData(size, size);
    for (let y = 0; y < size; y += 1) {
      for (let x = 0; x < size; x += 1) {
        const r = Math.hypot(x + 0.5 - size / 2, y + 0.5 - size / 2) / (size / 2);
        const a = r >= 1 ? 0 : r < 0.25 ? 1 : Math.pow(1 - (r - 0.25) / 0.75, 2);
        const o = (y * size + x) * 4;
        img.data[o] = 255;
        img.data[o + 1] = 255;
        img.data[o + 2] = 255;
        img.data[o + 3] = Math.round(a * 255);
      }
    }
    g.putImageData(img, 0, 0);
  }
  return new CanvasTexture(canvas);
}

/** Cooling colour of a spark: white-hot -> yellow -> amber -> deep orange, by age 0..1. */
function heat(t: number, out: Float32Array, o: number, alpha: number) {
  const r = 1;
  const g = Math.max(0.25, 1 - t * 0.85);
  const b = Math.max(0.05, 0.9 - t * 1.6);
  out[o] = r * alpha;
  out[o + 1] = g * alpha;
  out[o + 2] = b * alpha;
  out[o + 3] = alpha;
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
      renderer = new WebGLRenderer({ canvas, alpha: true, antialias: true, premultipliedAlpha: true, powerPreference: "low-power" });
    } catch {
      canvas.remove();
      return undefined;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.setClearColor(0x000000, 0);
    container.closest(".mk-foundry")?.classList.add("has-webgl");

    const scene = new Scene();
    const camera = new OrthographicCamera(0, 1, 0, 1, -1, 1);

    // Particle state (CSS pixels, y down).
    const px = new Float32Array(COUNT);
    const py = new Float32Array(COUNT);
    const vx = new Float32Array(COUNT);
    const vy = new Float32Array(COUNT);
    const age = new Float32Array(COUNT);
    const life = new Float32Array(COUNT);

    const headPos = new Float32Array(COUNT * 3);
    const headCol = new Float32Array(COUNT * 4);
    const trailPos = new Float32Array(COUNT * 6);
    const trailCol = new Float32Array(COUNT * 8);

    const heads = new BufferGeometry();
    heads.setAttribute("position", new BufferAttribute(headPos, 3));
    heads.setAttribute("color", new BufferAttribute(headCol, 4));
    const sprite = glowTexture();
    const headMaterial = new PointsMaterial({ size: 5, map: sprite, vertexColors: true, transparent: true, depthWrite: false, blending: AdditiveBlending, sizeAttenuation: false });
    const points = new Points(heads, headMaterial);

    const trails = new BufferGeometry();
    trails.setAttribute("position", new BufferAttribute(trailPos, 3));
    trails.setAttribute("color", new BufferAttribute(trailCol, 4));
    const trailMaterial = new LineBasicMaterial({ vertexColors: true, transparent: true, depthWrite: false, blending: AdditiveBlending });
    const lines = new LineSegments(trails, trailMaterial);
    scene.add(lines, points);

    let width = 1;
    let height = 1;
    const resize = () => {
      const { clientWidth: w, clientHeight: h } = canvas;
      if (!w || !h) return;
      width = w;
      height = h;
      renderer.setSize(w, h, false);
      camera.right = w;
      camera.bottom = h;
      camera.updateProjectionMatrix();
    };
    resize();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(resize);
    observer?.observe(canvas);

    const spawn = (i: number) => {
      const scale = width / 900;
      // Thrown mostly upwards and sideways out of the melt pool, a few skate down the curved surface.
      const angle = -Math.PI / 2 + (Math.random() - 0.5) * Math.PI * 1.35;
      const speed = (90 + Math.random() * 360) * scale;
      px[i] = width * HIT_X + (Math.random() - 0.5) * 4;
      py[i] = height * HIT_Y + (Math.random() - 0.5) * 3;
      vx[i] = Math.cos(angle) * speed;
      vy[i] = Math.sin(angle) * speed;
      age[i] = 0;
      life[i] = 0.35 + Math.random() * 0.9;
    };
    for (let i = 0; i < COUNT; i += 1) {
      spawn(i);
      age[i] = Math.random() * life[i];
    }

    let raf = 0;
    let last = 0;
    let slow = 0;
    let base = 0;
    let stopped = false;

    const frame = (now: number) => {
      const dtMs = last ? now - last : 16;
      last = now;
      if (dtMs > 0 && dtMs < 100) base = base ? base * 0.95 + Math.min(dtMs, base * 2) * 0.05 : dtMs;
      slow = dtMs > Math.max(SLOW_FRAME_MS, base * 1.5) ? slow + 1 : 0;
      const dt = Math.min(dtMs, 50) / 1000;
      const gravity = 520 * (width / 900);
      for (let i = 0; i < COUNT; i += 1) {
        age[i] += dt;
        if (age[i] >= life[i]) spawn(i);
        const ox = px[i];
        const oy = py[i];
        vy[i] += gravity * dt;
        vx[i] *= 0.995;
        px[i] += vx[i] * dt;
        py[i] += vy[i] * dt;
        const t = age[i] / life[i];
        const alpha = t < 0.08 ? t / 0.08 : 1 - t;
        headPos[i * 3] = px[i];
        headPos[i * 3 + 1] = py[i];
        heat(t, headCol, i * 4, alpha);
        // Streak from where the spark was a few frames ago (motion blur).
        const tail = 3.2;
        trailPos[i * 6] = px[i];
        trailPos[i * 6 + 1] = py[i];
        trailPos[i * 6 + 3] = px[i] - (px[i] - ox) * tail;
        trailPos[i * 6 + 4] = py[i] - (py[i] - oy) * tail;
        heat(t, trailCol, i * 8, alpha * 0.9);
        heat(Math.min(1, t + 0.3), trailCol, i * 8 + 4, 0);
      }
      const bail = slow >= SLOW_FRAME_LIMIT;
      if (bail) {
        // Too slow for this device: clear the sparks (the artwork and CSS layers stay), then stop.
        headCol.fill(0);
        trailCol.fill(0);
      }
      heads.attributes.position.needsUpdate = true;
      heads.attributes.color.needsUpdate = true;
      trails.attributes.position.needsUpdate = true;
      trails.attributes.color.needsUpdate = true;
      renderer.render(scene, camera);
      if (bail) {
        stopped = true;
        container.closest(".mk-foundry")?.classList.remove("has-webgl");
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
    // A reduced-motion request made while the boot is on screen stops the sparks at once (the picture stays).
    const motionQuery = typeof window.matchMedia === "function" ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
    const onMotion = () => {
      if (!motionQuery?.matches) return;
      stopped = true;
      cancelAnimationFrame(raf);
      headCol.fill(0);
      trailCol.fill(0);
      heads.attributes.color.needsUpdate = true;
      trails.attributes.color.needsUpdate = true;
      renderer.render(scene, camera);
      container.closest(".mk-foundry")?.classList.remove("has-webgl");
    };
    motionQuery?.addEventListener("change", onMotion);
    onVisibility();

    return () => {
      stopped = true;
      cancelAnimationFrame(raf);
      document.removeEventListener("visibilitychange", onVisibility);
      motionQuery?.removeEventListener("change", onMotion);
      observer?.disconnect();
      container.closest(".mk-foundry")?.classList.remove("has-webgl");
      heads.dispose();
      trails.dispose();
      headMaterial.dispose();
      trailMaterial.dispose();
      sprite.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
      canvas.remove();
    };
  }, []);

  // This layer is purely decorative.
  return <div ref={host} className="mk-boot-hero" aria-hidden="true" />;
}
