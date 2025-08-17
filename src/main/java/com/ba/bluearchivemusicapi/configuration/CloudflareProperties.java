package com.ba.bluearchivemusicapi.configuration;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Getter
@Setter
@Component
@ConfigurationProperties(prefix = "cloudflare.r2")
public class CloudflareProperties {
    private String endpoint;
    private String accessKey;
    private String secretKey;
    private String bucket;
}
