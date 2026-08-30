// Fragment Shader - Sophisticated Ambient Background
// Refined multi-layered design with subtle depth matching UI palette
#ifdef GL_ES
precision highp float;
#endif

uniform float uTime;
uniform vec2 uResolution;
varying vec2 vUv;

// ============================================================================
// Noise Functions
// ============================================================================

vec2 random2(vec2 st) {
    st = vec2(
        dot(st, vec2(127.1, 311.7)),
        dot(st, vec2(269.5, 183.3))
    );
    return -1.0 + 2.0 * fract(sin(st) * 43758.5453123);
}

float noise(vec2 st) {
    vec2 i = floor(st);
    vec2 f = fract(st);
    
    vec2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
    
    float a = dot(random2(i + vec2(0.0, 0.0)), f - vec2(0.0, 0.0));
    float b = dot(random2(i + vec2(1.0, 0.0)), f - vec2(1.0, 0.0));
    float c = dot(random2(i + vec2(0.0, 1.0)), f - vec2(0.0, 1.0));
    float d = dot(random2(i + vec2(1.0, 1.0)), f - vec2(1.0, 1.0));
    
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float fbm(vec2 st, int octaves) {
    float value = 0.0;
    float amplitude = 0.5;
    float frequency = 1.0;
    
    for (int i = 0; i < 6; i++) {
        if (i >= octaves) break;
        value += amplitude * noise(st * frequency);
        frequency *= 2.07;
        amplitude *= 0.52;
    }
    
    return value;
}

vec2 rotate(vec2 st, float angle) {
    float c = cos(angle);
    float s = sin(angle);
    return mat2(c, -s, s, c) * st;
}

// ============================================================================
// UI-Matched Color Palette - Professional dark theme
// ============================================================================

vec3 palette(float t) {
    // Matching the UI color scheme exactly
    vec3 a = vec3(0.045, 0.048, 0.072);  // Deep background
    vec3 b = vec3(0.065, 0.070, 0.095);  // Dark purple
    vec3 c = vec3(0.085, 0.088, 0.110);  // Medium purple-gray
    vec3 d = vec3(0.105, 0.108, 0.125);  // Lighter purple-gray
    vec3 e = vec3(0.125, 0.128, 0.145);  // Subtle highlight
    
    t = fract(t);
    
    if (t < 0.25) {
        return mix(a, b, t * 4.0);
    } else if (t < 0.5) {
        return mix(b, c, (t - 0.25) * 4.0);
    } else if (t < 0.75) {
        return mix(c, d, (t - 0.5) * 4.0);
    } else {
        return mix(d, e, (t - 0.75) * 4.0);
    }
}

// ============================================================================
// Gentle Flow Field
// ============================================================================

vec2 flowField(vec2 pos, float time) {
    float n1 = noise(pos * 1.5 + time * 0.05);
    float n2 = noise(pos * 2.0 - time * 0.06);
    return vec2(n1, n2) * 0.5;
}

// ============================================================================
// Main Shader - Ambient Background
// ============================================================================

void main() {
    vec2 st = vUv;
    float aspect = uResolution.x / uResolution.y;
    st.x *= aspect;
    
    vec2 pos = st - vec2(aspect * 0.5, 0.5);
    
    float t = uTime * 0.06;  // Slower, more calming motion
    
    // ========================================================================
    // Layer 1: Large ambient gradient base
    // ========================================================================
    vec2 flow1 = pos * 0.7;
    vec2 flowDir1 = flowField(flow1, t);
    flow1 += flowDir1 * 0.2;
    flow1 = rotate(flow1, t * 0.02);
    
    float noise1 = fbm(flow1 + t * 0.08, 4);
    
    // ========================================================================
    // Layer 2: Medium atmospheric depth
    // ========================================================================
    vec2 flow2 = pos * 1.5;
    vec2 flowDir2 = flowField(flow2, t * 0.8);
    flow2 += flowDir2 * 0.15;
    flow2 = rotate(flow2, -t * 0.03);
    
    float noise2 = fbm(flow2 - t * 0.1, 3);
    
    // ========================================================================
    // Layer 3: Subtle detail layer
    // ========================================================================
    vec2 flow3 = pos * 2.8;
    flow3 = rotate(flow3, t * 0.04);
    flow3 += flowField(flow3, t * 1.2) * 0.1;
    
    float noise3 = fbm(flow3 + t * 0.15, 3);
    
    // ========================================================================
    // Very subtle accent highlights
    // ========================================================================
    vec2 highlight = pos * 5.0;
    highlight = rotate(highlight, t * 0.08);
    float highlightNoise = noise(highlight + t * 0.25);
    highlightNoise = pow(max(highlightNoise, 0.0), 6.0) * 0.3;
    
    // ========================================================================
    // Combine layers - weighted toward ambient
    // ========================================================================
    float combined = 
        noise1 * 0.50 + 
        noise2 * 0.30 + 
        noise3 * 0.20;
    
    // Normalize
    combined = combined * 0.5 + 0.5;
    
    // Gentle breathing variation
    float breathe = sin(t * 0.15) * 0.04 + 0.5;
    combined = combined * 0.85 + breathe * 0.15;
    
    // ========================================================================
    // Soft expansive vignette
    // ========================================================================
    float dist = length(pos);
    float vignette = 1.0 - smoothstep(0.0, 2.2, dist);
    vignette = pow(vignette, 0.5);
    
    // Apply vignette
    combined *= vignette * 0.35 + 0.65;
    
    // ========================================================================
    // Map to refined color palette
    // ========================================================================
    vec3 color = palette(combined * 0.85);
    
    // ========================================================================
    // Subtle accent glow - matches UI purple accent
    // ========================================================================
    float accentGlow = pow(combined, 3.5) * 0.12;
    vec3 accentColor = vec3(0.15, 0.13, 0.20); // Subtle purple matching UI
    
    color += accentColor * accentGlow * vignette;
    
    // ========================================================================
    // Very subtle shimmer highlights
    // ========================================================================
    vec3 shimmerColor = vec3(0.14, 0.13, 0.18);
    color += shimmerColor * highlightNoise * vignette * 0.5;
    
    // ========================================================================
    // Extremely subtle depth variation
    // ========================================================================
    float depthShift = sin(combined * 3.14159 + t * 0.1) * 0.006;
    color.r += depthShift;
    color.b -= depthShift * 0.3;
    
    // ========================================================================
    // Gentle ambient pulse
    // ========================================================================
    float pulse = sin(t * 0.18) * 0.012 + 0.988;
    color *= pulse;
    
    // ========================================================================
    // Final color grading - keep it professional and dark
    // ========================================================================
    color = pow(color, vec3(1.02)); // Very slight contrast
    
    // Clamp to appropriate range for UI
    color = clamp(color, vec3(0.04, 0.045, 0.065), vec3(0.14, 0.145, 0.17));
    
    // Subtle desaturation for sophistication
    float luminance = dot(color, vec3(0.299, 0.587, 0.114));
    color = mix(vec3(luminance), color, 0.75 + vignette * 0.25);
    
    gl_FragColor = vec4(color, 1.0);
}
