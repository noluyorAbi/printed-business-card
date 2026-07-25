"use client";

import { OrbitControls } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { useMemo } from "react";
import * as THREE from "three";
import { SVGLoader } from "three/examples/jsm/loaders/SVGLoader.js";

import type { RenderResult, Solid } from "@/lib/spec";

/**
 * The card as the printer will make it.
 *
 * No mesh crosses the network: the worker sends the same layer outlines the
 * meshes are built from, and they are extruded here to their real z ranges.
 * That is what keeps a live edit at one small JSON round trip.
 */

function shapesFor(path: string): THREE.Shape[] {
  if (!path) return [];
  const parsed = new SVGLoader().parse(
    `<svg xmlns="http://www.w3.org/2000/svg"><path d="${path}"/></svg>`,
  );
  return parsed.paths.flatMap((p) => SVGLoader.createShapes(p));
}

function SolidMesh({ solid, color }: { solid: Solid; color: string }) {
  const geometry = useMemo(() => {
    const shapes = shapesFor(solid.d);
    if (!shapes.length) return null;
    const geo = new THREE.ExtrudeGeometry(shapes, {
      depth: solid.z1 - solid.z0,
      bevelEnabled: false,
      curveSegments: 6,
    });
    geo.translate(0, 0, solid.z0);
    geo.computeVertexNormals();
    return geo;
  }, [solid]);

  if (!geometry) return null;

  return (
    <mesh geometry={geometry} castShadow receiveShadow>
      <meshStandardMaterial color={color} roughness={0.72} metalness={0.02} />
    </mesh>
  );
}

export default function Card3D({ render }: { render: RenderResult }) {
  const { w, h } = render.card;
  const solids = render.solids.filter((s) => s.d);

  return (
    <Canvas
      shadows
      dpr={[1, 2]}
      camera={{ position: [0, -70, 62], fov: 34, up: [0, 0, 1] }}
      style={{ background: "transparent" }}
    >
      <ambientLight intensity={0.55} />
      <directionalLight position={[-40, -60, 90]} intensity={1.5} castShadow />
      <directionalLight position={[60, 30, 40]} intensity={0.4} />

      {/* the generator works from the lower left corner, so centre it here */}
      <group position={[-w / 2, -h / 2, 0]}>
        {solids.map((solid) => (
          <SolidMesh
            key={solid.id}
            solid={solid}
            color={render.colors[solid.filament]}
          />
        ))}
      </group>

      <OrbitControls
        makeDefault
        enablePan={false}
        minDistance={45}
        maxDistance={180}
        maxPolarAngle={Math.PI * 0.85}
      />
    </Canvas>
  );
}
