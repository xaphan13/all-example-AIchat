// Vertex Shader - Simple pass-through with UV coordinates
#ifdef GL_ES
precision highp float;
#endif

varying vec2 vUv;

void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}

