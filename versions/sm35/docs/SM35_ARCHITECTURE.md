# SM35 architecture

SM35 is an additive qualification layer over the immutable SM34 gzip member.
The release container concatenates the original SM34 gzip bytes with a second,
deterministic gzip member. Decompression therefore yields the complete SM34
stream first, followed by `SM35_STREAM_FRAMES_V1` content.

The internal architecture has five boundaries: strict receipts and finite
canonical JSON; content-addressed evidence and fixed Q01-Q10/B01-B20 scoring;
physical capability/authorization adapters; solver-neutral V&V contracts; and
streaming, confined reconstruction. Physical adapters never convert detection,
mocks, serial fallback, or local multi-process activity into qualification.

The Prompt Studio four-volume input is retained byte-for-byte as a reconstructed
single 7z artifact inside the SM35 frame layer. Its embedded SM34 release matches
the authoritative baseline hash. SM35 Prompt Studio changes are supplied only as
a versioned overlay, leaving all inherited application code intact.
