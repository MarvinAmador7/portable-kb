# Test fixtures

`reference-bundle/` is an isolated validation and lifecycle fixture. It is not
an installable Portable KB brain: this directory deliberately has no
`brain.yaml`, and the product repository must not gain one.

Tests copy the bundle into temporary brain repositories with synthetic
manifests and identities. Real user and organization knowledge belongs in
repositories created with `pkb brain init`, never in this source tree.
