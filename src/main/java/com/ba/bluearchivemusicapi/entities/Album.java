package com.ba.bluearchivemusicapi.entities;

import jakarta.persistence.*;
import lombok.*;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

@Setter
@Getter
@AllArgsConstructor
@NoArgsConstructor
@Entity
@Builder
@EntityListeners(AuditingEntityListener.class)
@Table(name = "album", uniqueConstraints = @UniqueConstraint(
        name = "uq_album_import_identity", columnNames = {"import_source", "source_album_id"}))
public class Album {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "title")
    private String title;

    @Column(name = "cover_image_path")
    private String coverImagePath;

    @Column(name = "cover_original_path")
    private String coverOriginalPath;

    @Column(name = "cover_400_path")
    private String cover400Path;

    @Column(name = "cover_800_path")
    private String cover800Path;

    @Column(name = "import_source", length = 64)
    private String importSource;

    @Column(name = "source_album_id", length = 255)
    private String sourceAlbumId;

    @Column(name = "release_date")
    private LocalDate releaseDate;

    @Column(name = "description", columnDefinition = "TEXT")
    private String description;

    @CreatedDate
    @Column(name = "created_date")
    private LocalDate createdDate;

    @LastModifiedDate
    @Column(name = "updated_date")
    private LocalDate updatedDate;

    @ManyToOne
    @JoinColumn(name = "category_id")
    private Category category;

    @OneToMany(mappedBy = "album")
    @OrderBy("displayOrder ASC, discNumber ASC, trackNumber ASC, id ASC")
    @Builder.Default
    private List<Song> songList = new ArrayList<>();

    // ──── Helper methods ────
    public void addSong(Song song) {
        songList.add(song);
        song.setAlbum(this);
    }

    public void removeSong(Song song) {
        songList.remove(song);
        song.setAlbum(null);
    }
}
