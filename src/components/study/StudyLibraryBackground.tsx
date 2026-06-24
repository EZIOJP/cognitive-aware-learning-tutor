import { useEffect, useRef } from "react";

const VS = `
  attribute vec4 aVertexPosition;
  varying vec2 v_texCoord;
  void main() {
    gl_Position = aVertexPosition;
    v_texCoord = aVertexPosition.xy * 0.5 + 0.5;
  }
`;

const FS = `
  precision highp float;
  uniform float u_time;
  uniform vec2 u_resolution;
  varying vec2 v_texCoord;

  float noise(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
  }

  void main() {
    vec2 uv = v_texCoord;
    vec3 color1 = vec3(0.02, 0.08, 0.06);
    vec3 color2 = vec3(0.06, 0.72, 0.51);
    vec3 color3 = vec3(0.0, 0.02, 0.01);
    float pulse = sin(u_time * 0.5) * 0.5 + 0.5;
    float motion = sin(uv.x * 3.0 + u_time * 0.2) * cos(uv.y * 2.0 - u_time * 0.3);
    float mask = smoothstep(0.2, 0.8, uv.y + motion * 0.1);
    vec3 finalColor = mix(color3, color1, uv.y);
    finalColor = mix(finalColor, color2 * 0.15, mask * pulse);
    finalColor += (noise(uv + u_time * 0.01) - 0.5) * 0.02;
    gl_FragColor = vec4(finalColor, 1.0);
  }
`;

function createShader(gl: WebGLRenderingContext, type: number, source: string) {
  const shader = gl.createShader(type);
  if (!shader) throw new Error("WebGL shader failed");
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  return shader;
}

export function StudyLibraryBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const gl = canvas.getContext("webgl");
    if (!gl) return;

    const vertexShader = createShader(gl, gl.VERTEX_SHADER, VS);
    const fragmentShader = createShader(gl, gl.FRAGMENT_SHADER, FS);
    const program = gl.createProgram();
    if (!program) return;
    gl.attachShader(program, vertexShader);
    gl.attachShader(program, fragmentShader);
    gl.linkProgram(program);
    gl.useProgram(program);

    const positionBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, 1, 1, 1, -1, -1, 1, -1]),
      gl.STATIC_DRAW,
    );

    const positionLocation = gl.getAttribLocation(program, "aVertexPosition");
    gl.enableVertexAttribArray(positionLocation);
    gl.vertexAttribPointer(positionLocation, 2, gl.FLOAT, false, 0, 0);

    const timeLocation = gl.getUniformLocation(program, "u_time");
    const resolutionLocation = gl.getUniformLocation(program, "u_resolution");

    let raf = 0;

    const resize = () => {
      canvas.width = canvas.clientWidth;
      canvas.height = canvas.clientHeight;
      gl.viewport(0, 0, canvas.width, canvas.height);
    };

    const render = (time: number) => {
      gl.uniform1f(timeLocation, time * 0.001);
      gl.uniform2f(resolutionLocation, canvas.width, canvas.height);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      raf = requestAnimationFrame(render);
    };

    resize();
    window.addEventListener("resize", resize);
    raf = requestAnimationFrame(render);

    return () => {
      window.removeEventListener("resize", resize);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full pointer-events-none"
      aria-hidden
    />
  );
}
