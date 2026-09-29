<p align="center"><img src="https://github.com/E2-RJ/Assets_ecosystem2/blob/main/Full_Logo/e2_full_logo_navy.svg" /></p>

This is part of the heart of borneo project, which uses a Fast API server to ingest climatology files and converts them into a file readable by cesium.

This is a development microservice, please read the contributions section for instrustions on collaborating.

## Development Instructions

Clone this repo, you should be within the development branch, and install [Python](https://www.python.org/downloads/).  

From the root directory of this repo, run:
```
Pretend there are python specific commands here
```

Typically hosted at `http://localhost:8000`, although this changes depending on the deployment method.

### Repository Structure
- development contains the new graphical elements and functionality needed to facilitate the user journey, expect this branch to be ever changing
- testing contains a more stable version of the development branch, this branch will be used to build and deploy UAT docker containers automatically.
- deployment contains the latest feature set we feel is ready and stable enough to be shown publically, the creation of a release is required before a docker container will be built.

If a particular feature will be very unstable/experiemntal, the best course of action would be to create a separate branch and merge back into the development branch once done.

### Folder Structure

## Testing/Unstable Instructions

In the future, a docker file and github workflow will be included within this repository. When a pull request is completed, the docker container is automatically built and submitted to [Dockerhub](https://hub.docker.com).

Once the changes made to the development branch are deemed stable enough for testing, a pull request can be made from the Testing branch (direct commits shall be blocked).

Once the image is built, it is automatically deployed to our testing servers.

## Production Instructions

In the future, a docker file and github workflow will be included within this repository. When a release is created, the docker container is built and submitted to [Dockerhub](https://hub.docker.com).

It is assumed you already have accounts for [Dockerhub](https://hub.docker.com) and [Github](https://github.com), along with a [Docker](https://www.docker.com/get-started/) instance set up for the built container to run on. If any information is needed on how ecosystem2 handles hosting, please reach to us via our [website](https://ecosystem2.co.uk) or [email](mailto:hello@ecosystem2.co.uk).

### Setting up dockerhub access token
- Once logged into Dockerhub, select the downward triangle next to your username on the far right of your screen.
  <p align="left"><img src="https://github.com/E2-RJ/Assets_ecosystem2/blob/main/Screenshot_Dockerhub-NavBar.png?raw=true" /></p>
- A dropdown should present itself, use this to **enter your account settings**
  <p align="left"><img src="https://github.com/E2-RJ/Assets_ecosystem2/blob/main/Screenshot_Dockerhub-Dropdown.png?raw=true" /></p>
- On the sidebar to the left, **Select Security**
  <p align="left"><img src="https://github.com/E2-RJ/Assets_ecosystem2/blob/main/Screenshot_Dockerhub-Security.png?raw=true" /></p>
- To the right of the Access Tokens heading, **Click on the blue New Access Token button**
  <p align="left"><img src="https://github.com/E2-RJ/Assets_ecosystem2/blob/main/Screenshot_Dockerhub-AddToken.png?raw=true" /></p>
- A popup should now appear in the centre of the screen, **Set the appropriate description and permissions**
  <p align="left"><img src="https://github.com/E2-RJ/Assets_ecosystem2/blob/main/Screenshot_Dockerhub-NewToken.png?raw=true" /></p>
- Your new token should now be created, **Copy the token**
  <p align="left"><img src="https://github.com/E2-RJ/Assets_ecosystem2/blob/main/Screenshot_Dockerhub-Token.png?raw=true" /></p>

### Setting up dockerhub credentials
- Below the repository name, in the top left corner of the screen, there is a navigation bar; **Select Settings**
  <p align="left"><img src="https://github.com/E2-RJ/Assets_ecosystem2/blob/main/Screenshot_Repo-Bar.png?raw=true" /></p>
- You should be presented with a page consisting with a sidbar and the repositories settings, **Select Secrets and variables**
  <p align="left"><img src="https://github.com/E2-RJ/Assets_ecosystem2/blob/main/Screenshot_RepoSettings-Sidebar.png?raw=true" /></p>
- With the sub-section expanded, **Select Actions**
  <p align="left"><img src="https://github.com/E2-RJ/Assets_ecosystem2/blob/main/Screenshot_Repo-Secrets.png?raw=true" /></p>
- This section **should already have two repository secrets, DOCKER_USERNAME and DOCKER_PASSWORD**
  <p align="left"><img src="https://github.com/E2-RJ/Assets_ecosystem2/blob/main/Screenshot_Docker_Credentials.png?raw=true" /></p>
- **If this is not the case, please add them**
- Assuming both secrets are present, **Select the pencil icon to edit each secret**

### Building docker container
- On the left sidebar, **Select Releases**
- **Select Draft New Release**
- Type in a new [version number](https://semver.org/) into tag field and select "Create new tag on publish".
- Set the target branch to production
- Either type the title and descript manually or select "Generate release notes"
- Press the green button that says "Publish release"
- Wait for the build to complete

#### Feel free to use the included docker-compose file, please note that it uses Traefik in order to create routes and assign SSL certificates. Although, any reverse proxy can be used or the container's ports exposed for direct access.

## Contributions

Pull requests are appreciated! Please use the same [Contributor License Agreement (CLA)](https://github.com/AnalyticalGraphicsInc/cesium/blob/master/CONTRIBUTING.md) and [Coding Guide](https://github.com/AnalyticalGraphicsInc/cesium/blob/master/Documentation/Contributors/CodingGuide/README.md) used for [Cesium](http://cesiumjs.org/).

## References

## Licence
Copyright (c) the respective contributors, as shown by the AUTHORS file.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
