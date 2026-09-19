// A stable WebXR local-floor frame is right-handed with -Z forward.
// The wire contract uses Unity convention: left-handed with +Z forward.
export function webXRWristToQuest(point: {x:number;y:number;z:number}) {
  if (![point.x,point.y,point.z].every(Number.isFinite)) return null;
  return {x:point.x,y:point.y,z:-point.z,visibility:1,inferred:false};
}
