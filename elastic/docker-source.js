// Docker json-file adds these labels only when configured in logging.options.
// Filter before publishing. No Docker API or Docker socket is needed.
var project;
var services = {api: "order-api", payment: "mock-payment", "db-init": "order-api", nginx: "nginx"};

function register(params) {
    project = params.project;
}

function process(event) {
    var docker = event.Get("docker");
    var attrs = docker && docker.attrs;
    var service = attrs && attrs["com.docker.compose.service"];
    if (!attrs || attrs["com.docker.compose.project"] !== project || !services[service]) {
        event.Cancel();
        return;
    }
    event.Put("message", docker.log.replace(/\n$/, ""));
    event.Put("log.iostream", docker.stream);
    event.Put("service.name", services[service]);
    event.Put("labels.compose_project", project);
    event.Put("labels.compose_service", service);
    event.Put("shopsphere.source", "container");
    event.Put("shopsphere.collected_time", docker.time);
    var path = event.Get("log.file.path");
    if (path) {
        event.Put("container.id", path.split("/")[4]);
    }
    event.Delete("docker");
}
