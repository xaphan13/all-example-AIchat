// Fragment Shader - Refined Ambient Background
// Subtle, professional design matching the UI color palette
#ifdef GL_ES
precision highp float;
#endif

uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

// Fast hash-based noise
float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

// Smooth noise
float noise(vec2 x) {
    vec2 i = floor(x);
    vec2 f = fract(x);
    f = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
    
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

// Simplified FBM - 3 octaves only
float fbm(vec2 p) {
    float f = 0.0;
    f += 0.5000 * noise(p); p *= 2.01;
    f += 0.2500 * noise(p); p *= 2.02;
    f += 0.1250 * noise(p);
    return f;
}

// UI-matched color palette - using exact colors from design system
vec3 getColor(float t) {
    // Deep space background
    vec3 a = vec3(0.045, 0.048, 0.072);  // Deep purple-black
    vec3 b = vec3(0.065, 0.070, 0.095);  // Dark purple
    vec3 c = vec3(0.085, 0.090, 0.115);  // Medium dark purple
    vec3 d = vec3(0.105, 0.110, 0.135);  // Lighter purple-gray
    
    t = fract(t);
    if (t < 0.33) {
        return mix(a, b, t * 3.0);
    } else if (t < 0.66) {
        return mix(b, c, (t - 0.33) * 3.0);
    } else {
        return mix(c, d, (t - 0.66) * 3.0);
    }
}

vec2 rotate(vec2 v, float a) {
    float c = cos(a);
    float s = sin(a);
    return mat2(c, -s, s, c) * v;
}

void main() {
    vec2 uv = vUv;
    float aspect = uResolution.x / uResolution.y;
    uv.x *= aspect;
    
    vec2 pos = uv - vec2(aspect * 0.5, 0.5);
    float t = uTime * 0.05; // Slower motion
    
    // Layer 1: Large slow-moving gradient
    vec2 flow1 = pos * 0.8;
    flow1 = rotate(flow1, t * 0.03);
    flow1.x += cos(t * 0.15) * 0.3;
    flow1.y += sin(t * 0.12) * 0.3;
    float n1 = fbm(flow1 + t * 0.08);
    
    // Layer 2: Medium ambient detail
    vec2 flow2 = pos * 1.8;
    flow2 = rotate(flow2, -t * 0.04);
    float n2 = fbm(flow2 - t * 0.1);
    
    // Combine with more weight on first layer
    float combined = n1 * 0.7 + n2 * 0.3;
    combined = combined * 0.5 + 0.5;
    
    // Softer, more expansive vignette
    float dist = length(pos);
    float vignette = 1.0 - smoothstep(0.0, 2.0, dist);
    vignette = pow(vignette, 0.6);
    combined *= vignette * 0.4 + 0.6;
    
    // Color mapping
    vec3 color = getColor(combined * 0.9);
    
    // Very subtle accent glow - matches UI purple
    float accentGlow = pow(combined, 4.0) * 0.08;
    vec3 accentColor = vec3(0.16, 0.14, 0.22); // Subtle purple accent
    color += accentColor * accentGlow * vignette;
    
    // Extremely subtle shimmer (less distracting)
    float shimmer = pow(max(noise(pos * 4.0 + t * 0.3), 0.0), 8.0) * 0.06;
    color += vec3(0.12, 0.11, 0.16) * shimmer * vignette;
    
    // Very subtle breathing pulse
    float pulse = sin(t * 0.2) * 0.008 + 0.992;
    color *= pulse;
    
    // Final adjustments - keep it dark and professional
    color = pow(color, vec3(1.0)); // No contrast adjustment
    color = clamp(color, vec3(0.04, 0.045, 0.065), vec3(0.12, 0.13, 0.16));
    
    gl_FragColor = vec4(color, 1.0);
}
