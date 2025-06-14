## waveform: OOK
Parameters:
 - `P` real samples per pulse
 - `N` repetition period - `M` sequence multiplier where `gcd(M,P)=1` (makes it sound less annoying & further increases frequency sep.)
 - `F=0,...,P/2`, frequency offset, so that the occupied band is `44.1e3*F/P - 44.1e3*(F+N-1)/P` Hz
   - however that wraps into DFT frequencies...

Transmission:
 - Tone pulses shaped by a Hamming window
 - For `b=1` at timeslot `t=0,1,2,...` transmit a length-`P` windowed tone with dft bin index `F+[ (M*t)%N ]`.
 - For `b=0` at timeslot `t=0,1,2,...` transmit nothing
