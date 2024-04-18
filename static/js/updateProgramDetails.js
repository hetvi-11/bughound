document.addEventListener("DOMContentLoaded", function () {
  // Check if an area and program_name are defined (from server-side rendering)
  if (document.getElementById("program").value) {
    updateProgramDetails(document.getElementById("program").value);
  }
});

function updateProgramDetails(programName) {
  const encodedProgramName = encodeURIComponent(
    programName || document.getElementById("program").value
  );
  fetch(`/get-program-details-by-name/${encodedProgramName}`)
    .then((response) => {
      if (response.ok) {
        return response.json();
      } else {
        throw new Error("Failed to fetch data");
      }
    })
    .then((data) => {
      const versionSelect = document.getElementById("program-version");
      const releaseSelect = document.getElementById("program-release");

      versionSelect.innerHTML = "";
      releaseSelect.innerHTML = "";

      if (data.versions) {
        data.versions.forEach((version) => {
          versionSelect.appendChild(new Option(version, version));
        });
      }

      if (data.releases) {
        data.releases.forEach((release) => {
          releaseSelect.appendChild(new Option(release, release));
        });
      }
    })
    .catch((error) => console.error("Error:", error));
}
