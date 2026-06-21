package com.ba.bluearchivemusicapi.configuration;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(useDefaultFilters = false)
@Import({SecurityConfig.class, AdminApiKeySecurityTest.TestAdminController.class})
@TestPropertySource(properties = "app.admin.api-key=test-admin-key")
class AdminApiKeySecurityTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void rejectsAdminRequestWithoutApiKey() throws Exception {
        mockMvc.perform(get("/admin/test"))
                .andExpect(status().isForbidden());
    }

    @Test
    void rejectsAdminRequestWithWrongApiKey() throws Exception {
        mockMvc.perform(get("/admin/test")
                        .header("X-Admin-Api-Key", "wrong-key"))
                .andExpect(status().isForbidden());
    }

    @Test
    void allowsAdminRequestWithCorrectApiKey() throws Exception {
        mockMvc.perform(get("/admin/test")
                        .header("X-Admin-Api-Key", "test-admin-key"))
                .andExpect(status().isOk());
    }

    @RestController
    @RequestMapping("/admin/test")
    static class TestAdminController {

        @GetMapping
        ResponseEntity<String> get() {
            return ResponseEntity.ok("OK");
        }
    }
}
