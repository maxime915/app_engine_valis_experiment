"""Pre-download the pytorch model weights used by valis at build time so the
runtime image does not need to fetch them (and does not need network access)."""

from valis import feature_detectors, feature_matcher

print("Downloading DiskFD weights")
disk_fd = feature_detectors.DiskFD()
print("Downloading DeDoDeFD weights")
dedode_fd = feature_detectors.DeDoDeFD()

feature_matcher.LightGlueMatcher(disk_fd)
feature_matcher.LightGlueMatcher(dedode_fd)
