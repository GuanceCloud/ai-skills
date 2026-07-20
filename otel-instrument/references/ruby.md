# Ruby repositories

## Detection

Map `Gemfile`, `Gemfile.lock`, `.ruby-version`, gemspecs, Rails/Rack/Sinatra boot paths, background jobs, scheduled tasks, forking and threaded servers, dependency clients, logging, and existing telemetry. Treat independently deployed web and worker processes as modules.

## Implementation

- Prefer the official OpenTelemetry Ruby SDK, OTLP exporter, and official/upstream instrumentation gems for dependencies actually loaded.
- Initialize one provider early enough for framework instrumentation and preserve existing logging. Do not double-instrument libraries already covered.
- Handle preloading and post-fork initialization deliberately, and flush telemetry during server, worker, and task shutdown.
- Add manual spans only around meaningful application services, jobs, consumers, and outbound boundaries not covered automatically.
- Gate each signal on the current official Ruby maturity and compatible gem set; skip and document unavailable signals.

## Dependency decisions

Verify RubyGems ownership, official source links, supported Ruby/framework versions, and dependency constraints. Select the newest compatible official release, preserve Bundler and the lockfile, and do not silently upgrade Ruby or frameworks.

## Validation

Run Bundler-native formatting/lint, tests such as RSpec or Minitest, application boot, and representative web/job flows. Test preloaded/forked workers when used. Verify propagation, log correlation where selected, exporter flush, error recording, and representative inbound-to-outbound or producer-to-consumer context.
