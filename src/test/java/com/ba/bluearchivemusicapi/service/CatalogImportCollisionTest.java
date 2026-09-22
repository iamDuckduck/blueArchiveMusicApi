package com.ba.bluearchivemusicapi.service;

import org.hibernate.exception.ConstraintViolationException;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DataIntegrityViolationException;

import java.sql.SQLException;

import static org.assertj.core.api.Assertions.assertThat;

class CatalogImportCollisionTest {
    @Test
    void onlyAlbumIdentityUniqueViolationsAreRetryable() {
        assertThat(CatalogImportService.isAlbumIdentityCollision(failure("23505", "uq_album_import_identity"))).isTrue();
        // H2 reports the backing index name rather than just the constraint name.
        assertThat(CatalogImportService.isAlbumIdentityCollision(failure("23505", "PUBLIC.UQ_ALBUM_IMPORT_IDENTITY_INDEX_3"))).isTrue();
        assertThat(CatalogImportService.isAlbumIdentityCollision(failure("23505", "uq_other_constraint"))).isFalse();
        assertThat(CatalogImportService.isAlbumIdentityCollision(failure("23502", "uq_album_import_identity"))).isFalse();
        assertThat(CatalogImportService.isAlbumIdentityCollision(failure("23505", null))).isFalse();
        assertThat(CatalogImportService.isAlbumIdentityCollision(new DataIntegrityViolationException("unknown"))).isFalse();
    }

    private DataIntegrityViolationException failure(String sqlState, String constraint) {
        return new DataIntegrityViolationException("test violation",
                new ConstraintViolationException("test violation", new SQLException("test", sqlState), constraint));
    }
}
