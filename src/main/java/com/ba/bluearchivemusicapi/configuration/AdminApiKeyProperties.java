package com.ba.bluearchivemusicapi.configuration;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app.admin")
public record AdminApiKeyProperties(String apiKey) {
}
