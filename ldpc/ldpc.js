// QC-IRA LDPC encoder (n=1024, k=512) for browser use
export class Encoder1024R12 {
  constructor(Z = 32){
    this.Z = Z; this.BR = 16; this.BC = 32;
    this.M = this.BR * Z; this.N = this.BC * Z; this.K = this.N - this.M;
    this.ROTS = Int16Array.from([1,5,9,13,3,7,11,15,2,6,10,14,4,8,12,16]);
    this.Hu = this._buildHu();
    this._s = new Uint8Array(this.M);
    this._p = new Uint8Array(this.M);
    this._cw = new Uint8Array(this.N);
  }
  encode(u){
    if (!(u instanceof Uint8Array) || u.length !== this.K) throw new Error(`u must be Uint8Array len ${this.K}`);
    const Z=this.Z, BR=this.BR;
    this._s.fill(0);
    for (let r=0;r<this.M;r++){
      let acc=0; const cols=this.Hu[r];
      for (let i=0;i<cols.length;i++) acc ^= (u[cols[i]] & 1);
      this._s[r]=acc;
    }
    this._p.fill(0);
    this._rotXorInto(this._s, 0, this._p, 0, this.ROTS[0]);
    for (let i=1;i<BR;i++){
      const off=i*Z, prev=(i-1)*Z;
      for (let z=0;z<Z;z++) this._p[off+z] = this._s[off+z] ^ this._p[prev+z];
      this._rotateInPlace(this._p, off, Z, this.ROTS[i]);
    }
    this._cw.set(u, 0); this._cw.set(this._p, this.K);
    return this._cw.slice();
  }
  _buildHu(){
    const Z=this.Z, BR=this.BR, info_bc=this.BC-this.BR;
    const rows=Array.from({length:BR*Z},()=>[]);
    for (let i=0;i<BR;i++){
      for (let t=0;t<6;t++){
        const j=(i*3 + t*5) % info_bc;
        const shift=(11*i + 7*j + 3) % Z;
        for (let z=0;z<Z;z++){
          const r=i*Z + z;
          const c=j*Z + ((z + shift) % Z);
          rows[r].push(c);
        }
      }
    }
    for (let r=0;r<rows.length;r++){
      rows[r].sort((a,b)=>a-b);
      const out=[]; let last=-1;
      for (let i=0;i<rows[r].length;i++){ const v=rows[r][i]; if (v!==last) { out.push(v); last=v; } }
      rows[r]=out;
    }
    return rows;
  }
  _rotXorInto(src, sOff, dst, dOff, r){
    const Z=this.Z; const s=((r%Z)+Z)%Z;
    if (s===0){ for (let i=0;i<Z;i++) dst[dOff+i] ^= src[sOff+i]; }
    else { for (let i=0;i<Z;i++){ const j=(i - s + Z) % Z; dst[dOff+i] ^= src[sOff+j]; } }
  }
  _rotateInPlace(a, off, len, r){
    const Z=len, s=((r%Z)+Z)%Z; if (s===0) return;
    const tmp=a.slice(off+Z-s, off+Z); a.copyWithin(off+s, off, off+Z-s); a.set(tmp, off);
  }
}
