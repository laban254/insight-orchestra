# Changelog

## [1.0.1](https://github.com/laban254/insight-orchestra/compare/v1.0.0...v1.0.1) (2026-09-03)


### Bug Fixes

* **agents:** report LLM fallback instead of presenting it as analysis ([01cff5c](https://github.com/laban254/insight-orchestra/commit/01cff5c671970588779b66f4ac608a263e035957))
* **agents:** treat dates as time, not as a category ([e5f1668](https://github.com/laban254/insight-orchestra/commit/e5f166888dd9914546b6c99e8c55f86619517bba))
* **connectors:** enforce read-only at the session level, decode credentials ([fe99f44](https://github.com/laban254/insight-orchestra/commit/fe99f4408949fd982dfbd304028f9522411ad1d2))
* **connectors:** make SQLite and DuckDB usable from the container ([feaf7d6](https://github.com/laban254/insight-orchestra/commit/feaf7d6f9f5615b3fa7db248302898f31ddb02a3))
* **ingest:** sniff encoding and delimiter, parse dates on read ([e9a8b21](https://github.com/laban254/insight-orchestra/commit/e9a8b21078edcaed0cea3bdc5a33d34185df708d))
* **landing:** resolve mobile overflow, lead with demo, raise contrast ([7757d9f](https://github.com/laban254/insight-orchestra/commit/7757d9f6dba06ca4b2b0b1539c6a3c2227d58f6c))
* **ops:** cap container logs and refresh the Anthropic model default ([da068ef](https://github.com/laban254/insight-orchestra/commit/da068efc9b5486431f125783e963cca086fc28df))
* resolve all 13 open CodeQL code scanning alerts ([f3df29e](https://github.com/laban254/insight-orchestra/commit/f3df29ea448bede8d6466f01db3bfd87f8f62e80))
* **retention:** reap idle datasets and sweep orphaned upload files ([63e2ea3](https://github.com/laban254/insight-orchestra/commit/63e2ea3758df76d8f9f6ea8faaf302b35d4b7d00))
* run a single uvicorn worker so agent progress actually streams ([22c631e](https://github.com/laban254/insight-orchestra/commit/22c631e4f404d7caa43a0d2391d11744a0b8942f)), closes [#53](https://github.com/laban254/insight-orchestra/issues/53)
* **security:** delete the dead second FastAPI app ([4b2a9fa](https://github.com/laban254/insight-orchestra/commit/4b2a9fadcc7de96cec0ce2e2f732e0ef3a4cf58c))
* **security:** drop the isfile pre-check that CodeQL kept flagging ([95b4270](https://github.com/laban254/insight-orchestra/commit/95b4270ab14fc95f4ec9caf3db3c2974a080cbdd))
* **security:** harden the code sandbox and resolve post-review findings ([6a6c71a](https://github.com/laban254/insight-orchestra/commit/6a6c71a914253759eab2c026fcc7cdb9ce7052bf))
* **security:** inline the allowed-dir check for CodeQL guard recognition ([4d8726e](https://github.com/laban254/insight-orchestra/commit/4d8726ec5ba3be7b4a084c6e7e01f34532661f8f))
* **security:** split path-injection guard into sequential checks ([a033e18](https://github.com/laban254/insight-orchestra/commit/a033e182e9c016a66bcfd65615a6d4a9a63ef14c))
* stop presenting LLM-fallback output as completed analysis ([9929721](https://github.com/laban254/insight-orchestra/commit/99297216a80202f2c0852f66c659badda78ced28))
* stop reporting a healthy backend as broken on first run ([a49b991](https://github.com/laban254/insight-orchestra/commit/a49b991385896dec778ef4937b6247f21cc9df51))
* stop reporting a healthy backend as broken on first run ([81e2a8d](https://github.com/laban254/insight-orchestra/commit/81e2a8d88fe1762168cff89784b95648e8e4fb18))
* type error in dataset preview response ([0616179](https://github.com/laban254/insight-orchestra/commit/061617949bc251ddae44127804c22bf1871391fd))
* type error in dataset preview response ([1ada26c](https://github.com/laban254/insight-orchestra/commit/1ada26cadb83c9dad97212674d5d8f06aafe1838))
* **ui:** render unscored results honestly and label icon-only controls ([fdb9422](https://github.com/laban254/insight-orchestra/commit/fdb9422ec1f67e518fc8e80e8ad420ff9643ccc0))
* **upload:** validate content properly and report what was ingested ([35b4538](https://github.com/laban254/insight-orchestra/commit/35b4538d0d70f47db248e98cd77e9539154d999a))


### Performance Improvements

* **hypothesis:** cap columns fed to the fallback's O(n^2) loops ([e8b3d0a](https://github.com/laban254/insight-orchestra/commit/e8b3d0a95886ec4a357d151ee09e8e0ee0527dd0))
* **nlq:** cache the cleaned frame instead of re-cleaning per question ([47b9074](https://github.com/laban254/insight-orchestra/commit/47b90745d30cad398d0fd67de24e90634aa8fdc7))
* **pipeline:** pass DataFrames between agents instead of dicts ([cc24350](https://github.com/laban254/insight-orchestra/commit/cc2435069963c4b154590d3b9831bbd411b512ce))

## [1.0.0](https://github.com/laban254/insight-orchestra/compare/v0.1.0...v1.0.0) (2026-08-19)


### Features

* Add an improvement roadmap detailing multi-database connectors and Ollama local LLM support. ([a21281e](https://github.com/laban254/insight-orchestra/commit/a21281eec7c6d3e41e499723f6c1f3a9f56c5133))
* add BigQuery data source option and enhance sidebar navigation ([0960e34](https://github.com/laban254/insight-orchestra/commit/0960e344be7dc5147fb96dd8b44741d54619b53b))
* add initial README with project overview and setup instructions ([25e4ea0](https://github.com/laban254/insight-orchestra/commit/25e4ea09c7aba67caec5c0374303dd347571198f))
* Add new frontend dependencies ([3544745](https://github.com/laban254/insight-orchestra/commit/3544745ee4048192ff2deb4c89eb3538fa4b4de3))
* Add new frontend dependencies ([af3c455](https://github.com/laban254/insight-orchestra/commit/af3c455d602393af41a6c210e1b28bc7ddf146a5))
* Add new frontend dependencies ([c7cce08](https://github.com/laban254/insight-orchestra/commit/c7cce08d646847a7e9f2f1fad54f6377f9eae73e))
* add one-command setup and devcontainer support ([449ce41](https://github.com/laban254/insight-orchestra/commit/449ce41728ccc8c60b8b0bc63149f063de0bd343))
* add one-command setup and devcontainer support ([1670606](https://github.com/laban254/insight-orchestra/commit/1670606ad6b43fe340cfc27b028b891550189886))
* add one-line installer and enhance agent outputs ([bc429e9](https://github.com/laban254/insight-orchestra/commit/bc429e9391a526a82cd3d01022ba5f9231a2e508))
* Add unit tests for agent LLM integration ([8ee038b](https://github.com/laban254/insight-orchestra/commit/8ee038b07ad3880aaf091bb7f3d2fada6ff50482))
* Add unit tests for agent LLM integration ([ffe4e8d](https://github.com/laban254/insight-orchestra/commit/ffe4e8df60f5f5bee7579a9a3c9ee4a6d53f6d77))
* Add unit tests for agent LLM integration ([515e3f3](https://github.com/laban254/insight-orchestra/commit/515e3f389d20218cd784d84d87129b373ab24fe9))
* **agents:** add audit table and refine hypothesis output ([181ef6a](https://github.com/laban254/insight-orchestra/commit/181ef6abe1f3e96309e977a5345850522588b31e))
* **agents:** add audit table and refine hypothesis output ([9904e96](https://github.com/laban254/insight-orchestra/commit/9904e96aa746a6dbff913b9de75e1ede59c0fe08))
* **connectors:** add database table loading and connection management ([a5fc512](https://github.com/laban254/insight-orchestra/commit/a5fc512486322b61a2a0a10546a4a5fd47eef289))
* **connectors:** add database table loading and connection management ([4e1a7e1](https://github.com/laban254/insight-orchestra/commit/4e1a7e146b33c415e344b7d1c4bdc90b66da0475))
* enhance agent pipeline with new PipelineBlock component and integrate live agent updates in ChatPanel ([3108974](https://github.com/laban254/insight-orchestra/commit/3108974bab9eb86b36d92654b94e7e31899169ec))
* enhance sidebar navigation and styling ([5932635](https://github.com/laban254/insight-orchestra/commit/59326355a435291d4fccad83c3f354fd4b713a42))
* **export:** add shareable session links and CSV export ([d043146](https://github.com/laban254/insight-orchestra/commit/d0431467affdcfef8c27e28a9d5be0fb83aa439a))
* **export:** add shareable session links and CSV export ([da00c07](https://github.com/laban254/insight-orchestra/commit/da00c07ad4a5583323a105b96eb050b1305760cc))
* implement 4-phase roadmap — connectors, Ollama, React UI, exports & sharing ([2119d56](https://github.com/laban254/insight-orchestra/commit/2119d563b3ee1c055a9e63fa35117fa04057bcea))
* implement 4-phase roadmap — connectors, Ollama, React UI, exports & sharing ([a1be45f](https://github.com/laban254/insight-orchestra/commit/a1be45fd66e8b94dcb4704c61f8c34b95844a3b7))
* publish prebuilt images and pull them by default ([f903ca3](https://github.com/laban254/insight-orchestra/commit/f903ca3ba62a7f8163e7c9e64ee2135e3e24b877))
* publish prebuilt images and pull them by default ([323d3c7](https://github.com/laban254/insight-orchestra/commit/323d3c780ec3dff949a2df4890c4c210e65914e9))
* update  documentation ([d7d44db](https://github.com/laban254/insight-orchestra/commit/d7d44db283edaa9f1c62522038aaa93c624768eb))
* Update architecture and setup documentation ([187b359](https://github.com/laban254/insight-orchestra/commit/187b3590029981def7f711f59ddc2013df8eab98))
* updated frontend dependencies and Docker Compose configurations. ([4ae689b](https://github.com/laban254/insight-orchestra/commit/4ae689b082bd308ad660dbacc3b6212880ddcc7e))
* updated frontend dependencies and Docker Compose configurations. ([e3b5644](https://github.com/laban254/insight-orchestra/commit/e3b56442e932e93b1b9aaa979f1601cef1faec59))
* workspace experience overhaul — canvas flow, persistence, export, model switcher ([dc3ac0f](https://github.com/laban254/insight-orchestra/commit/dc3ac0f9566a566b297861cdb809b014696f1b39))
* workspace experience overhaul — canvas flow, persistence, export, model switcher ([65b9f47](https://github.com/laban254/insight-orchestra/commit/65b9f479671d977fda186c8870c4e562e000300e))
* **workspace:** add server-side workspace persistence ([8e44bcc](https://github.com/laban254/insight-orchestra/commit/8e44bccac3b53156956f62bde7ab6a36c95fbc92))
* **workspace:** add server-side workspace persistence ([d6066e7](https://github.com/laban254/insight-orchestra/commit/d6066e703cc9fc8eba48c1549ab7a531639472cf))


### Bug Fixes

* add z-index to header to prevent overlap issues ([c1ffc37](https://github.com/laban254/insight-orchestra/commit/c1ffc37bed1215c63807e1a28223a27f9ab20132))
* **api:** guard against null hypotheses in export ([306764f](https://github.com/laban254/insight-orchestra/commit/306764fc0e5a797acf57fccdcec354b61afa1afe))
* better error handling in install and setup ([1f5a7c8](https://github.com/laban254/insight-orchestra/commit/1f5a7c8fb3c3e004649228faeb23398b032fd1f5))
* better error handling in install and setup ([24a5a51](https://github.com/laban254/insight-orchestra/commit/24a5a513fc89e1200fa327b15936ec12501e25de))
* **demo:** correct sales dataset column count metadata ([4936c4a](https://github.com/laban254/insight-orchestra/commit/4936c4a9d964d2448812a7410474b3ffd578bfee))
* **frontend:** resolve the backend URL at runtime ([2a45777](https://github.com/laban254/insight-orchestra/commit/2a45777160e09b7747e8519a09f0aa423688e2e4))
* **frontend:** resolve the backend URL at runtime ([f5e5284](https://github.com/laban254/insight-orchestra/commit/f5e5284ee5a677f7ea20384cacac31c3b18a4236))
* **nlq:** display user-friendly auth error message ([ef28ec9](https://github.com/laban254/insight-orchestra/commit/ef28ec960132b344effb879a2be967f0ff6bc71a))
* **nlq:** display user-friendly auth error message ([1a230dd](https://github.com/laban254/insight-orchestra/commit/1a230dd1f34f85822b9e0f3566f087c5ec4d1057))
* **nlq:** handle Ollama connection errors gracefully ([cfbfdf6](https://github.com/laban254/insight-orchestra/commit/cfbfdf66618f7b444846c6fe299e90c6cb770ac2))
* **nlq:** handle Ollama connection errors gracefully ([72f5ef7](https://github.com/laban254/insight-orchestra/commit/72f5ef780fc954a1a6824dd21cf3673e179fae21))
* **scripts:** accept standalone docker-compose v2 ([a4ee481](https://github.com/laban254/insight-orchestra/commit/a4ee481894491c84dd8bbbaf6528fa27af5f645f))
* **scripts:** accept standalone docker-compose v2 ([44b4f04](https://github.com/laban254/insight-orchestra/commit/44b4f049d172dfa6bdce722a1d690ff36c24e474))
* **setup:** improve port check handling and error messages during ser… ([780fd32](https://github.com/laban254/insight-orchestra/commit/780fd328478a3a2880cc19d7af61a1b9bbd7ea2c))
* **setup:** improve port check handling and error messages during service startup ([74b0123](https://github.com/laban254/insight-orchestra/commit/74b01232ad89f996dbbc2be9460d942c5cdbf325))
* **workspace:** return metadata only on list endpoint ([5fcf247](https://github.com/laban254/insight-orchestra/commit/5fcf24777b642af66550299b0a8f540718e1c146))


### Miscellaneous Chores

* release 1.0.0 ([47e9693](https://github.com/laban254/insight-orchestra/commit/47e969362c1213eaf92453adf1dca9d7a0e4be17))
