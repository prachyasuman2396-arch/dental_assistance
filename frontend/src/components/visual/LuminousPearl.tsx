"use client";

import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";

interface LuminousPearlProps {
  className?: string;
  size?: number;
}

export function LuminousPearl({ className = "", size = 260 }: LuminousPearlProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [hasWebGL, setHasWebGL] = useState<boolean>(true);

  useEffect(() => {
    if (!containerRef.current) return;

    // Check WebGL availability
    try {
      const canvas = document.createElement("canvas");
      const gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
      if (!gl) {
        setHasWebGL(false);
        return;
      }
    } catch {
      setHasWebGL(false);
      return;
    }

    const container = containerRef.current;
    const width = size;
    const height = size;

    // 1. Scene & Camera
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.z = 5.2;

    // 2. Renderer
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // 3. Central Pearl Sphere
    const sphereGeo = new THREE.SphereGeometry(1.3, 64, 64);
    
    // Iridescent Pearlescent Material
    const sphereMat = new THREE.MeshPhysicalMaterial({
      color: new THREE.Color("#F4F1FA"),
      emissive: new THREE.Color("#8D79D6"),
      emissiveIntensity: 0.18,
      roughness: 0.15,
      metalness: 0.1,
      clearcoat: 1.0,
      clearcoatRoughness: 0.1,
      transmission: 0.65, // translucent pearl feel
      ior: 1.5,
      reflectivity: 0.9,
    });
    const pearl = new THREE.Mesh(sphereGeo, sphereMat);
    scene.add(pearl);

    // 4. Subtle Inner Glow Core
    const innerGeo = new THREE.SphereGeometry(0.85, 32, 32);
    const innerMat = new THREE.MeshBasicMaterial({
      color: new THREE.Color("#DCD3FF"),
      transparent: true,
      opacity: 0.35,
    });
    const innerCore = new THREE.Mesh(innerGeo, innerMat);
    scene.add(innerCore);

    // 5. Delicate Orbital Rings
    const ringGroup = new THREE.Group();
    
    const ringMat1 = new THREE.MeshBasicMaterial({
      color: new THREE.Color("#B6A4FF"),
      transparent: true,
      opacity: 0.45,
      wireframe: false,
    });
    const ringGeo1 = new THREE.TorusGeometry(2.0, 0.018, 16, 100);
    const ring1 = new THREE.Mesh(ringGeo1, ringMat1);
    ring1.rotation.x = Math.PI / 3;
    ring1.rotation.y = Math.PI / 6;
    ringGroup.add(ring1);

    const ringMat2 = new THREE.MeshBasicMaterial({
      color: new THREE.Color("#9EC9FF"),
      transparent: true,
      opacity: 0.35,
    });
    const ringGeo2 = new THREE.TorusGeometry(2.35, 0.014, 16, 100);
    const ring2 = new THREE.Mesh(ringGeo2, ringMat2);
    ring2.rotation.x = -Math.PI / 4;
    ring2.rotation.y = -Math.PI / 5;
    ringGroup.add(ring2);

    scene.add(ringGroup);

    // 6. Floating Micro-particles
    const particleCount = 45;
    const particleGeo = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);

    for (let i = 0; i < particleCount * 3; i += 3) {
      const radius = 2.0 + Math.random() * 1.2;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(Math.random() * 2 - 1);

      positions[i] = radius * Math.sin(phi) * Math.cos(theta);
      positions[i + 1] = radius * Math.sin(phi) * Math.sin(theta);
      positions[i + 2] = radius * Math.cos(phi);
    }
    particleGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));

    const particleMat = new THREE.PointsMaterial({
      color: new THREE.Color("#DCD3FF"),
      size: 0.04,
      transparent: true,
      opacity: 0.65,
    });
    const particles = new THREE.Points(particleGeo, particleMat);
    scene.add(particles);

    // 7. Lighting
    const ambientLight = new THREE.AmbientLight("#EDE7F6", 1.2);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight("#DDE8FF", 2.2);
    dirLight1.position.set(4, 5, 4);
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight("#F3DDEB", 1.8);
    dirLight2.position.set(-4, -3, 2);
    scene.add(dirLight2);

    // 8. Pointer Tracking for gentle parallax
    let mouseX = 0;
    let mouseY = 0;
    let targetX = 0;
    let targetY = 0;

    const onPointerMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      mouseX = ((e.clientX - rect.left) / width - 0.5) * 0.8;
      mouseY = ((e.clientY - rect.top) / height - 0.5) * 0.8;
    };

    window.addEventListener("pointermove", onPointerMove);

    // 9. Animation Loop
    let animId: number;
    let clock = new THREE.Clock();

    const animate = () => {
      animId = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();

      // Gentle floating
      pearl.position.y = Math.sin(elapsed * 0.9) * 0.08;
      innerCore.position.y = pearl.position.y;

      // Smooth pointer parallax
      targetX += (mouseX - targetX) * 0.04;
      targetY += (mouseY - targetY) * 0.04;

      pearl.rotation.y = elapsed * 0.15 + targetX * 0.5;
      pearl.rotation.x = targetY * 0.3;

      // Slow orbital ring rotation
      ringGroup.rotation.y = elapsed * 0.08 + targetX * 0.4;
      ringGroup.rotation.x = Math.sin(elapsed * 0.05) * 0.1 + targetY * 0.2;

      // Subtle particle swirl
      particles.rotation.y = -elapsed * 0.05;

      renderer.render(scene, camera);
    };

    animate();

    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      cancelAnimationFrame(animId);
      if (renderer.domElement && container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      renderer.dispose();
      sphereGeo.dispose();
      sphereMat.dispose();
      innerGeo.dispose();
      innerMat.dispose();
      ringGeo1.dispose();
      ringGeo2.dispose();
      ringMat1.dispose();
      ringMat2.dispose();
      particleGeo.dispose();
      particleMat.dispose();
    };
  }, [size]);

  if (!hasWebGL) {
    // Beautiful pure CSS / SVG fallback
    return (
      <div
        className={`relative flex items-center justify-center ${className}`}
        style={{ width: size, height: size }}
      >
        <div className="w-32 h-32 rounded-full bg-gradient-to-tr from-violet-300 via-white to-purple-200 pearl-glow animate-pulse" />
        <div className="absolute inset-0 border border-violet-300/30 rounded-full animate-spin [animation-duration:15s]" />
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`relative flex items-center justify-center select-none pointer-events-none ${className}`}
      style={{ width: size, height: size }}
      aria-label="Study AI Luminous Orb"
    />
  );
}
