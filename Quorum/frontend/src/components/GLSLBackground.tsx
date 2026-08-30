/**
 * GLSLBackground - Sophisticated ambient backgroundc
 * 
 * Uses Three.js with refined gradients and subtle depth effects.
 * Elegant, professional design that complements the UI without distraction.
 * 
 * Features:
 * - Smooth radial gradients with depth
 * - Gentle color transitions
 * - Subtle animated orbs for ambience
 * - Performance-optimized rendering
 */

import { useRef, useMemo } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';

/**
 * Refined gradient shader - smooth, no noise
 */
const sophisticatedShader = {
  vertexShader: `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: `
    uniform float uTime;
    uniform vec2 uResolution;
    varying vec2 vUv;
    
    // Smooth color palette matching UI
    vec3 getBaseColor(vec2 uv) {
      // Deep purple-black base
      vec3 color1 = vec3(0.047, 0.050, 0.075);
      vec3 color2 = vec3(0.070, 0.073, 0.095);
      vec3 color3 = vec3(0.090, 0.093, 0.115);
      
      // Create smooth radial gradient
      vec2 center = vec2(0.5, 0.5);
      float dist = length(uv - center);
      
      // Gentle breathing effect
      float breathe = sin(uTime * 0.3) * 0.015 + 0.985;
      dist *= breathe;
      
      // Smooth color transitions
      float t = smoothstep(0.0, 1.5, dist);
      vec3 color = mix(color3, color1, t);
      
      // Add subtle directional gradient
      float dirGrad = (uv.y * 0.4 + uv.x * 0.1) * 0.08;
      color += vec3(dirGrad);
      
      return color;
    }
    
    // Soft orb influence for ambient depth
    float softOrb(vec2 uv, vec2 pos, float radius, float softness) {
      float dist = length(uv - pos);
      return smoothstep(radius + softness, radius - softness, dist);
    }
    
    void main() {
      vec2 uv = vUv;
      float aspect = uResolution.x / uResolution.y;
      uv.x *= aspect;
      
      // Base gradient
      vec3 color = getBaseColor(vUv);
      
      // Animated orbs for subtle depth (very gentle)
      float t = uTime * 0.15;
      
      // Orb 1 - top right
      vec2 orb1Pos = vec2(
        aspect * 0.7 + cos(t * 0.8) * 0.15,
        0.75 + sin(t * 0.6) * 0.1
      );
      float orb1 = softOrb(uv, orb1Pos, 0.3, 0.4);
      vec3 orb1Color = vec3(0.14, 0.12, 0.20);
      color += orb1Color * orb1 * 0.15;
      
      // Orb 2 - bottom left
      vec2 orb2Pos = vec2(
        aspect * 0.25 + sin(t * 0.5) * 0.12,
        0.3 + cos(t * 0.7) * 0.08
      );
      float orb2 = softOrb(uv, orb2Pos, 0.35, 0.45);
      vec3 orb2Color = vec3(0.12, 0.11, 0.18);
      color += orb2Color * orb2 * 0.12;
      
      // Orb 3 - center ambient
      vec2 orb3Pos = vec2(
        aspect * 0.5 + cos(t * 0.4) * 0.08,
        0.55 + sin(t * 0.5) * 0.06
      );
      float orb3 = softOrb(uv, orb3Pos, 0.4, 0.5);
      vec3 orb3Color = vec3(0.15, 0.13, 0.21);
      color += orb3Color * orb3 * 0.10;
      
      // Soft vignette
      vec2 centered = vUv - vec2(0.5);
      float vignette = 1.0 - dot(centered, centered) * 0.8;
      vignette = smoothstep(0.3, 1.0, vignette);
      color *= vignette * 0.85 + 0.15;
      
      // Keep colors in professional range
      color = clamp(color, vec3(0.045), vec3(0.16));
      
      gl_FragColor = vec4(color, 1.0);
    }
  `,
};

/**
 * Gradient plane with sophisticated shader
 */
function GradientPlane() {
  const meshRef = useRef<THREE.Mesh>(null);
  const { viewport } = useThree();

  const shaderMaterial = useMemo(() => {
    return new THREE.ShaderMaterial({
      vertexShader: sophisticatedShader.vertexShader,
      fragmentShader: sophisticatedShader.fragmentShader,
      uniforms: {
        uTime: { value: 0 },
        uResolution: { value: new THREE.Vector2(window.innerWidth, window.innerHeight) },
      },
      side: THREE.DoubleSide,
    });
  }, []);

  useMemo(() => {
    shaderMaterial.uniforms.uResolution.value.set(window.innerWidth, window.innerHeight);
  }, [viewport.width, viewport.height, shaderMaterial]);

  useFrame((state) => {
    if (meshRef.current && meshRef.current.material instanceof THREE.ShaderMaterial) {
      meshRef.current.material.uniforms.uTime.value = state.clock.elapsedTime;
    }
  });

  return (
    <mesh ref={meshRef} material={shaderMaterial}>
      <planeGeometry args={[viewport.width, viewport.height, 1, 1]} />
    </mesh>
  );
}

/**
 * Subtle floating particles for depth (optional, very minimal)
 */
function AmbientParticles() {
  const particlesRef = useRef<THREE.Points>(null);
  const { viewport } = useThree();

  const [positions, colors] = useMemo(() => {
    const count = 30; // Very few particles, just for ambience
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    
    const color1 = new THREE.Color(0.15, 0.13, 0.20);
    const color2 = new THREE.Color(0.12, 0.11, 0.18);
    
    for (let i = 0; i < count; i++) {
      // Spread across viewport
      positions[i * 3] = (Math.random() - 0.5) * viewport.width;
      positions[i * 3 + 1] = (Math.random() - 0.5) * viewport.height;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 2;
      
      // Alternate colors
      const color = i % 2 === 0 ? color1 : color2;
      colors[i * 3] = color.r;
      colors[i * 3 + 1] = color.g;
      colors[i * 3 + 2] = color.b;
    }
    
    return [positions, colors];
  }, [viewport.width, viewport.height]);

  useFrame((state) => {
    if (!particlesRef.current) return;
    
    // Gentle float animation
    const time = state.clock.elapsedTime * 0.1;
    const positions = particlesRef.current.geometry.attributes.position.array as Float32Array;
    
    for (let i = 0; i < positions.length; i += 3) {
      const idx = i / 3;
      positions[i + 1] += Math.sin(time + idx * 0.5) * 0.0005;
    }
    
    particlesRef.current.geometry.attributes.position.needsUpdate = true;
    particlesRef.current.rotation.z = Math.sin(time * 0.2) * 0.01;
  });

  return (
    <points ref={particlesRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={positions.length / 3}
          array={positions}
          itemSize={3}
        />
        <bufferAttribute
          attach="attributes-color"
          count={colors.length / 3}
          array={colors}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.015}
        vertexColors
        transparent
        opacity={0.4}
        sizeAttenuation
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

/**
 * GLSLBackground - Main component
 * Sophisticated ambient background with subtle depth
 */
export function GLSLBackground() {
  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        zIndex: -1,
        pointerEvents: 'none',
      }}
    >
      <Canvas
        camera={{ position: [0, 0, 5], fov: 50 }}
        gl={{
          antialias: true, // Smooth gradients need antialiasing
          alpha: false,
          powerPreference: 'high-performance',
        }}
        dpr={Math.min(window.devicePixelRatio, 2)}
      >
        <GradientPlane />
        <AmbientParticles />
      </Canvas>
    </div>
  );
}

